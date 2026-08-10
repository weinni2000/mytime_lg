import base64
import json
from datetime import date

from werkzeug.exceptions import NotFound

from odoo.exceptions import ValidationError
from odoo.http import request, route
from odoo.tools.image import image_process

from odoo.addons.camping_map_booking.models.camping_map_state import (
    STATE_FREE,
    STATE_NOT_SUITABLE,
    STATE_OCCUPIED,
)
from odoo.addons.website_sale.controllers.cart import Cart
from odoo.addons.website_sale.controllers.main import WebsiteSale

CAMPING_STEP_HREF = "/shop/camping"
PITCH_STEP_HREF = "/shop/pitch"
DOG_SPECIES_XMLID = "animal.dog"
DOG_PRODUCT_XMLID = "camping_checkout.product_dog"
ADDITIONAL_GUEST_PRODUCT_XMLID = "camping_checkout.product_additional_guest"
LOCAL_TAX_MIN_AGE = 16


class WebsiteSaleCampingCheckout(WebsiteSale):
    def _parse_form_data(self, form_data):
        id_document_front = form_data.pop("x_id_document_front", None)
        address_values, extra_form_data = super()._parse_form_data(form_data)

        if id_document_front and getattr(id_document_front, "filename", ""):
            address_values["x_id_document_front"] = base64.b64encode(id_document_front.read())

        return address_values, extra_form_data

    def _get_mandatory_billing_address_fields(self, country_sudo):
        mandatory_fields = super()._get_mandatory_billing_address_fields(country_sudo)
        if self._needs_address():
            mandatory_fields = mandatory_fields | {"birthdate_date"}
        return mandatory_fields

    def _prepare_address_form_values(self, *args, **kwargs):
        rendering_values = super()._prepare_address_form_values(*args, **kwargs)
        countries = rendering_values.get("countries")
        if countries is not None:
            priority_countries = countries.filtered(lambda c: c.x_checkout_priority_sequence).sorted(
                key=lambda c: c.x_checkout_priority_sequence
            )
            rendering_values["priority_countries"] = priority_countries
            rendering_values["countries"] = countries - priority_countries
        return rendering_values

    # === CHECKOUT FLOW - CAMPING STEP METHODS === #

    @route([CAMPING_STEP_HREF], type="http", auth="public", website=True, sitemap=False)
    def shop_camping(self, **post):
        order_sudo = request.cart
        redirection = self._check_cart(order_sudo)
        if redirection:
            return redirection

        sudo_env = request.env(su=True)
        dog_species = sudo_env.ref(DOG_SPECIES_XMLID, raise_if_not_found=False)
        values = {
            "website_sale_order": order_sudo,
            "order": order_sudo,
            "vehicle": order_sudo.vehicle_ids[:1],
            "vehicle_categories": request.env["camping.vehicle.type"].sudo().search([]),
            "dogs": order_sudo.animal_ids,
            "with_electricity": self._has_camping_electricity(order_sudo),
            "dog_breeds": sudo_env["animal.breed"].search(
                [("species_id", "=", dog_species.id)] if dog_species else []
            ),
            "guest_rows": self._get_camping_guest_rows(order_sudo),
        }
        values.update(request.website._get_checkout_step_values())

        return request.render("camping_checkout.camping_step", values)

    @route()
    def shop_payment_validate(self, sale_order_id=None, **post):
        order_sudo = (
            request.env["sale.order"].sudo().browse(sale_order_id).exists()
            if sale_order_id
            else request.cart
            or request.env["sale.order"].sudo().browse(request.session.get("sale_last_order_id")).exists()
        )
        response = super().shop_payment_validate(sale_order_id=sale_order_id, **post)
        if (
            order_sudo
            and order_sudo.state in ("draft", "sent")
            and order_sudo.company_id.x_use_camping_pitch_map
            and order_sudo.pitch_resource_id
        ):
            transaction = order_sudo.get_portal_last_transaction()
            if transaction and transaction.provider_id.code == "custom" and transaction.state == "pending":
                order_sudo.action_confirm()
        return response

    def _get_camping_guest_rows(self, order_sudo):
        main_guest_line = order_sudo.x_guest_line_ids.filtered(
            lambda guest: guest.x_main_guest and guest.x_guest_partner_id == order_sudo.partner_id
        )[:1]
        companion_lines = order_sudo.x_guest_line_ids.filtered(lambda g: not g.x_main_guest)

        birthdate = order_sudo.partner_id.birthdate_date
        main_row = {
            "name": order_sudo.partner_id.name,
            "age": (
                self._age_from_birthdate(birthdate)
                if birthdate
                else main_guest_line.x_guest_age
                if main_guest_line
                else order_sudo.partner_id.x_age
            ),
        }
        rows = [main_row] + [{"name": g.x_guest_name, "age": g.x_guest_age} for g in companion_lines]
        return rows

    @route(
        [f"{CAMPING_STEP_HREF}/submit"],
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        sitemap=False,
    )
    def shop_camping_submit(self, **post):
        order_sudo = request.cart
        redirection = self._check_cart(order_sudo)
        if redirection:
            return redirection

        category_id = post.get("x_vehicle_category_id")
        if category_id:
            vehicle_vals = {
                "category_id": int(category_id),
            }
            vehicle_sudo = order_sudo.vehicle_ids[:1]
            if vehicle_sudo:
                vehicle_sudo.write(vehicle_vals)
            else:
                request.env["camping.fleet.vehicle"].sudo().create(
                    {
                        **vehicle_vals,
                        "sale_order_id": order_sudo.id,
                    }
                )

        self._update_camping_dogs(order_sudo, post)
        self._update_electricity_product(order_sudo, post.get("x_with_electricity") == "on")
        guest_count, adult_guest_count = self._update_camping_guests(order_sudo)
        self._update_additional_guest_product(order_sudo, guest_count)
        self._update_local_tax_product(order_sudo, adult_guest_count)

        current_step = request.website._get_checkout_step(CAMPING_STEP_HREF)
        next_step = current_step._get_next_checkout_step(request.website._get_allowed_steps_domain())
        return request.redirect(next_step.step_href or "/shop/payment")

    def _update_camping_dogs(self, order_sudo, post):
        with_dogs = post.get("x_with_dogs") == "on"
        breed_ids = []
        if with_dogs:
            for breed_id in request.httprequest.form.getlist("x_dog_breed_id"):
                if breed_id.isdigit():
                    breed_ids.append(int(breed_id))

        order_sudo.animal_ids.sudo().unlink()

        sudo_env = request.env(su=True)
        dog_product = sudo_env.ref(DOG_PRODUCT_XMLID, raise_if_not_found=False)
        breeds = sudo_env["animal.breed"].browse(breed_ids).exists()
        if breeds:
            request.env["animal"].sudo().create(
                [
                    {
                        "name": "Dog",
                        "species_id": breed.species_id.id,
                        "breed_id": breed.id,
                        "product_id": dog_product.id if dog_product else False,
                        "sale_order_id": order_sudo.id,
                    }
                    for breed in breeds
                ]
            )

        if dog_product:
            self._set_camping_product_quantity(order_sudo, dog_product, len(breeds))

    def _set_camping_product_quantity(self, order_sudo, product, quantity):
        existing_line = order_sudo._cart_find_product_line(product.id, uom_id=product.uom_id.id)[:1]
        if existing_line:
            order_sudo._cart_update_line_quantity(line_id=existing_line.id, quantity=quantity)
        elif quantity > 0:
            order_sudo._cart_add(
                product_id=product.id,
                quantity=quantity,
                start_date=order_sudo.rental_start_date,
                end_date=order_sudo.rental_return_date,
            )

    @staticmethod
    def _get_camping_electricity_product(order_sudo):
        accommodation_lines = order_sudo.order_line.filtered(
            lambda line: line.product_id.product_tmpl_id.x_electricity_product_id
        )
        return accommodation_lines.product_id.product_tmpl_id.x_electricity_product_id[:1]

    def _has_camping_electricity(self, order_sudo):
        electricity_product = self._get_camping_electricity_product(order_sudo)
        return bool(
            electricity_product
            and order_sudo._cart_find_product_line(electricity_product.id, uom_id=electricity_product.uom_id.id)
        )

    def _update_electricity_product(self, order_sudo, selected):
        electricity_product = self._get_camping_electricity_product(order_sudo)
        if electricity_product:
            self._set_camping_product_quantity(order_sudo, electricity_product, int(selected))

    def _update_camping_guests(self, order_sudo):
        """Save the submitted guest rows and return (total_guests, adult_guests).

        The first row always represents the ordering customer: it's only ever
        used to make sure a main guest line exists, never to rename/edit the
        actual billing contact. Remaining rows are saved as companion guests.
        Age is required on every row, so every counted guest has a known age.
        """
        names = request.httprequest.form.getlist("x_guest_name")
        ages = request.httprequest.form.getlist("x_guest_age")

        sudo_env = request.env(su=True)
        main_guest_lines = order_sudo.x_guest_line_ids.filtered(lambda guest: guest.x_main_guest)
        main_guest_line = (
            main_guest_lines.filtered(lambda guest: guest.x_guest_partner_id == order_sudo.partner_id)[:1]
            or main_guest_lines[:1]
        )
        if main_guest_line and main_guest_line.x_guest_partner_id != order_sudo.partner_id:
            main_guest_line.sudo().x_guest_partner_id = order_sudo.partner_id
        elif not main_guest_line and order_sudo.partner_id:
            main_guest_line = sudo_env["x_guests_line"].create(
                {
                    "x_sale_order_id": order_sudo.id,
                    "x_guest_partner_id": order_sudo.partner_id.id,
                    "x_main_guest": True,
                }
            )

        guest_ages = []
        if order_sudo.partner_id.birthdate_date:
            guest_ages.append(self._age_from_birthdate(order_sudo.partner_id.birthdate_date))
        elif ages and ages[0].isdigit():
            guest_ages.append(int(ages[0]))

        guest_vals = []
        for name, age in zip(names[1:], ages[1:], strict=False):
            name = (name or "").strip()
            if not name:
                continue
            vals = {"name": name}
            if age.isdigit():
                age_int = int(age)
                vals["birthdate_date"] = self._birthdate_from_age(age_int)
                guest_ages.append(age_int)
            guest_vals.append(vals)

        order_sudo.x_guest_line_ids.filtered(lambda g: not g.x_main_guest).sudo().unlink()

        for vals in guest_vals:
            partner = sudo_env["res.partner"].create(vals)
            sudo_env["x_guests_line"].create(
                {
                    "x_sale_order_id": order_sudo.id,
                    "x_guest_partner_id": partner.id,
                    "x_main_guest": False,
                }
            )

        total_guests = 1 + len(guest_vals)
        adult_guests = sum(1 for age in guest_ages if age >= LOCAL_TAX_MIN_AGE)
        return total_guests, adult_guests

    def _update_additional_guest_product(self, order_sudo, guest_count):
        sudo_env = request.env(su=True)
        extra_product = sudo_env.ref(ADDITIONAL_GUEST_PRODUCT_XMLID, raise_if_not_found=False)
        if not extra_product:
            return

        accommodation_lines = order_sudo.order_line.filtered(
            lambda line: line.product_id.product_tmpl_id.x_additional_guest_product_id
        )
        if not accommodation_lines:
            return

        max_guest_total = sum(line.product_uom_qty * line.product_id.x_max_guest for line in accommodation_lines)
        extra_qty = max(guest_count - max_guest_total, 0)
        self._set_camping_product_quantity(order_sudo, extra_product, extra_qty)

    def _update_local_tax_product(self, order_sudo, adult_guest_count):
        tax_product = order_sudo.company_id.x_local_tax_product_id
        if not tax_product:
            return
        nights = 0
        if order_sudo.rental_start_date and order_sudo.rental_return_date:
            # Camping stays run evening check-in to morning check-out, e.g. 20:00 to
            # 07:00 the next day: barely 11 elapsed hours, but a full night's stay.
            # duration_days (raw elapsed time) would round that down to 0 nights, so
            # nights are counted by calendar date instead.
            nights = (order_sudo.rental_return_date.date() - order_sudo.rental_start_date.date()).days
        self._set_camping_product_quantity(order_sudo, tax_product, adult_guest_count * max(nights, 0))

    @staticmethod
    def _age_from_birthdate(birthdate):
        today = date.today()
        return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))

    @staticmethod
    def _birthdate_from_age(age):
        today = date.today()
        try:
            return today.replace(year=today.year - age)
        except ValueError:
            # today is Feb 29 and the birth year isn't a leap year
            return today.replace(year=today.year - age, day=28)


class WebsiteSaleCampingCart(Cart):
    def cart(self, *args, **kwargs):
        # The "Address" step was moved before "Cart" (see hooks._reorder_cart_step), so a
        # customer who reaches /shop/cart via the header cart icon or the "View Cart" add-to-cart
        # notification before ever filling in an address should be sent there first.
        order_sudo = request.cart
        if order_sudo and order_sudo._is_anonymous_cart():
            return request.redirect("/shop/address")

        return super().cart(*args, **kwargs)


class WebsiteSaleCampingPitch(WebsiteSale):
    @route(
        ["/shop/pitch/map/<int:map_id>/image"],
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def shop_pitch_map_image(self, map_id):
        campsite_map = request.env["campsite.map"].sudo().browse(map_id).exists()
        if not campsite_map or not campsite_map.active or not campsite_map.image:
            raise NotFound()
        attachment = (
            request.env["ir.attachment"]
            .sudo()
            .search(
                [
                    ("res_model", "=", "campsite.map"),
                    ("res_id", "=", campsite_map.id),
                    ("res_field", "=", "image"),
                ],
                order="id desc",
                limit=1,
            )
        )
        return request.make_response(
            image_process(base64.b64decode(campsite_map.image), size=(1024, 1024)),
            headers=[
                ("Content-Type", attachment.mimetype or "image/png"),
                ("Cache-Control", "public, max-age=86400"),
            ],
        )

    def _get_pitch_page_values(self, order_sudo, error=None):
        vehicle = order_sudo.vehicle_ids[:1]
        campsite_map = request.env["campsite.map"].sudo().search([("active", "=", True)], order="id", limit=1)
        # Single source of truth for state labels/colors (occupied = yellow, etc.).
        state_labels = {
            code: colors["label"] for code, colors in request.env["camping.map.state"]._get_frontend_map().items()
        }
        shapes = []
        if campsite_map:
            for zone in campsite_map.zone_ids.filtered(lambda item: item.active and item.points):
                items = []
                for resource in zone.resource_ids:
                    state = zone._get_resource_state(
                        resource,
                        vehicle.category_id,
                        order_sudo.rental_start_date,
                        order_sudo.rental_return_date,
                    )
                    items.append(
                        {
                            "id": resource.id,
                            "name": resource.name,
                            "price": "",
                            "url": False,
                            "state": state,
                            "state_label": state_labels.get(state, ""),
                            "selectable": state == STATE_FREE,
                        }
                    )
                zone_states = {item["state"] for item in items}
                state = (
                    STATE_FREE
                    if STATE_FREE in zone_states
                    else STATE_OCCUPIED
                    if STATE_OCCUPIED in zone_states
                    else STATE_NOT_SUITABLE
                )
                shape = zone._get_map_shapes(state)[0]
                shape["products"] = items
                shapes.append(shape)

        values = {
            "website_sale_order": order_sudo,
            "order": order_sudo,
            "vehicle": vehicle,
            "vehicle_types": request.env["camping.vehicle.type"].sudo().search([]),
            "campsite_map": campsite_map,
            "zones_json": json.dumps(shapes),
            "map_image_url": (
                f"/shop/pitch/map/{campsite_map.id}/image?preview=1024&unique={campsite_map.write_date.timestamp()}"
                if campsite_map and campsite_map.image
                else "/camping_map_booking/static/src/img/camping_map.png"
            ),
            "selected_pitch": order_sudo.pitch_resource_id,
            "map_legend_json": json.dumps(campsite_map._get_availability_legend()) if campsite_map else "[]",
            "map_legend_position": campsite_map._legend_position() if campsite_map else "none",
            "error": error,
        }
        values.update(request.website._get_checkout_step_values())
        return values

    @route([PITCH_STEP_HREF], type="http", auth="public", website=True, sitemap=False)
    def shop_pitch(self, **post):
        order_sudo = request.cart
        redirection = self._check_cart(order_sudo)
        if redirection:
            return redirection
        if not order_sudo.company_id.x_use_camping_pitch_map:
            return request.redirect("/shop/cart")
        if not order_sudo.vehicle_ids:
            return request.redirect(CAMPING_STEP_HREF)
        return request.render(
            "camping_checkout.pitch_step",
            self._get_pitch_page_values(order_sudo),
        )

    @route(
        [f"{PITCH_STEP_HREF}/submit"],
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        sitemap=False,
    )
    def shop_pitch_submit(self, **post):
        order_sudo = request.cart
        redirection = self._check_cart(order_sudo)
        if redirection:
            return redirection
        if not order_sudo.company_id.x_use_camping_pitch_map:
            return request.redirect("/shop/cart")

        pitch_id = post.get("pitch_resource_id")
        pitch = (
            request.env["resource.resource"].sudo().browse(int(pitch_id)).exists()
            if pitch_id and pitch_id.isdigit()
            else request.env["resource.resource"]
        )
        if not pitch:
            return request.render(
                "camping_checkout.pitch_step",
                self._get_pitch_page_values(order_sudo, error="Please select an available pitch."),
            )

        order_sudo.pitch_resource_id = pitch
        try:
            order_sudo._validate_pitch_selection()
        except ValidationError as error:
            order_sudo.pitch_resource_id = False
            return request.render(
                "camping_checkout.pitch_step",
                self._get_pitch_page_values(order_sudo, error=str(error)),
            )

        current_step = request.website._get_checkout_step(PITCH_STEP_HREF)
        next_step = current_step._get_next_checkout_step(request.website._get_allowed_steps_domain())
        return request.redirect(next_step.step_href or "/shop/cart")
