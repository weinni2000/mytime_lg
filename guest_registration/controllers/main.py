import base64
from datetime import timedelta

from odoo import _, fields
from odoo.exceptions import UserError
from odoo.http import Controller, request, route
from odoo.tools import consteq


class GuestRegistrationController(Controller):
    def _get_order_sudo(self, order_id, access_token):
        order_sudo = request.env["sale.order"].sudo().browse(order_id).exists()
        if (
            not order_sudo
            or not access_token
            or not order_sudo.access_token
            or not consteq(order_sudo.access_token, access_token)
        ):
            return None
        return order_sudo

    @staticmethod
    def _read_upload(storage):
        return base64.b64encode(storage.read()) if storage and storage.filename else False

    @staticmethod
    def _scan_result_values(partner_sudo):
        return {
            "name": partner_sudo.name or "",
            "birthdate": partner_sudo.birthdate_date.isoformat() if partner_sudo.birthdate_date else "",
            "street": partner_sudo.street or "",
            "zip": partner_sudo.zip or "",
            "city": partner_sudo.city or "",
            "country_id": partner_sudo.country_id.id or "",
        }

    def _get_companion_rows(self, order_sudo):
        rows = []
        for guest in order_sudo._get_guest_registration_companions():
            partner = guest.x_guest_partner_id
            rows.append(
                {
                    "id": guest.id,
                    "name": partner.name or "",
                    "is_child": guest.x_is_child,
                }
            )
        return rows

    @route(
        "/guest_registration/<int:order_id>",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def guest_registration_form(self, order_id, access_token=None, **kwargs):
        order_sudo = self._get_order_sudo(order_id, access_token)
        if not order_sudo:
            return request.render("guest_registration.guest_registration_invalid_link")

        today = fields.Date.context_today(request.env.user)
        values = {
            "order": order_sudo,
            "access_token": access_token,
            "countries": request.env["res.country"].sudo().search([], order="name"),
            "companion_guests": self._get_companion_rows(order_sudo),
            "products": request.env["product.product"]
            .sudo()
            .search([("product_tmpl_id.x_is_a_room_offer", "=", True)], order="name"),
            "journals": request.env["account.journal"]
            .sudo()
            .search([("type", "in", ("bank", "cash"))], order="name"),
            "default_start_date": (
                order_sudo.rental_start_date.date() if order_sudo.rental_start_date else today
            ).isoformat(),
            "default_end_date": (
                order_sudo.rental_return_date.date()
                if order_sudo.rental_return_date
                else today + timedelta(days=1)
            ).isoformat(),
        }
        return request.render("guest_registration.guest_registration_page", values)

    @route(
        "/guest_registration/<int:order_id>/submit",
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        sitemap=False,
    )
    def guest_registration_submit(self, order_id, access_token=None, **post):
        order_sudo = self._get_order_sudo(order_id, access_token)
        if not order_sudo:
            return request.render("guest_registration.guest_registration_invalid_link")

        country_id = post.get("country_id", "")
        birthdate = post.get("birthdate")
        order_sudo._update_guest_registration_address(
            {
                "name": post.get("name"),
                "street": post.get("street"),
                "zip": post.get("zip"),
                "city": post.get("city"),
                "country_id": int(country_id) if country_id.isdigit() else False,
                "phone": post.get("phone"),
                "email": post.get("email"),
                "birthdate_date": fields.Date.to_date(birthdate) if birthdate else False,
            }
        )

        names = request.httprequest.form.getlist("guest_name")
        is_child_flags = request.httprequest.form.getlist("guest_is_child")
        line_ids = request.httprequest.form.getlist("guest_line_id")
        rows = [
            {
                "line_id": line_id,
                "name": name,
                "is_child": is_child == "1",
            }
            for name, is_child, line_id in zip(names, is_child_flags, line_ids, strict=False)
        ]
        order_sudo._update_guest_registration_companions(rows)

        product_id = post.get("product_id", "")
        journal_id = post.get("journal_id", "")
        start_date = post.get("rental_start_date")
        end_date = post.get("rental_return_date")
        order_sudo._update_guest_registration_booking(
            int(product_id) if product_id.isdigit() else False,
            int(journal_id) if journal_id.isdigit() else False,
            post.get("immediate_payment") == "on",
            fields.Datetime.to_datetime(start_date) if start_date else False,
            fields.Datetime.to_datetime(end_date) if end_date else False,
        )

        return request.redirect(f"/odoo/sale.order/{order_sudo.id}")

    @route(
        "/guest_registration/<int:order_id>/search_location",
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        sitemap=False,
    )
    def guest_registration_search_location(self, order_id, access_token=None, query=None, **post):
        order_sudo = self._get_order_sudo(order_id, access_token)
        if not order_sudo:
            return request.make_json_response({"error": _("Invalid or expired link.")}, status=403)

        query = (query or "").strip()
        if len(query) < 2:
            return request.make_json_response([])

        locations = (
            request.env["res.city.zip"]
            .sudo()
            .search(["|", ("name", "ilike", query), ("city_id.name", "ilike", query)], limit=10)
        )
        return request.make_json_response(
            [
                {
                    "id": location.id,
                    "display_name": location.display_name,
                    "zip": location.name,
                    "city": location.city_id.name,
                    "country_id": location.city_id.country_id.id,
                }
                for location in locations
            ]
        )

    @route(
        "/guest_registration/<int:order_id>/scan_id",
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        sitemap=False,
    )
    def guest_registration_scan_id(self, order_id, access_token=None, **post):
        order_sudo = self._get_order_sudo(order_id, access_token)
        if not order_sudo:
            return request.make_json_response({"error": _("Invalid or expired link.")}, status=403)

        front = self._read_upload(request.httprequest.files.get("id_document_front"))
        back = self._read_upload(request.httprequest.files.get("id_document_back"))
        if not front and not back:
            return request.make_json_response(
                {"error": _("Upload a front or back image of the document first.")}, status=400
            )

        values = {}
        if front:
            values["x_id_document_front"] = front
        if back:
            values["x_id_document_back"] = back

        partner_sudo = order_sudo.partner_id.sudo()
        partner_sudo.write(values)
        try:
            partner_sudo.action_scan_id_documents()
        except UserError as error:
            return request.make_json_response({"error": str(error)}, status=400)

        return request.make_json_response(self._scan_result_values(partner_sudo))
