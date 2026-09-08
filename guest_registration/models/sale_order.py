from odoo import Command, _, api, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_guest_registration_url(self):
        self.ensure_one()
        self._portal_ensure_token()
        return f"{self.get_base_url()}/guest_registration/{self.id}?access_token={self.access_token}"

    @api.model
    def action_open_guest_registration_form(self):
        partner = self.env["res.partner"].create({"name": _("New Guest")})
        order = self.create({"partner_id": partner.id})
        return order.action_open_guest_registration_wizard()

    def action_open_guest_registration_link(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "guest.registration.link.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_sale_order_id": self.id},
        }

    def action_open_guest_registration_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "guest.registration.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_sale_order_id": self.id},
        }

    def action_send_guest_registration_email(self):
        template = self.env.ref("guest_registration.mail_template_guest_registration", raise_if_not_found=False)
        if not template:
            raise UserError(_("The guest registration email template is missing."))
        for order in self:
            if not order.partner_id.email:
                raise UserError(
                    _(
                        "The customer %(partner)s has no email address.",
                        partner=order.partner_id.display_name,
                    )
                )
            template.send_mail(order.id, force_send=True, raise_exception=True)
        return True

    def _get_guest_registration_companions(self):
        self.ensure_one()
        return self.x_guest_line_ids.filtered(lambda guest: guest.x_guest_partner_id != self.partner_id)

    def _update_guest_registration_address(self, values):
        self.ensure_one()
        values = {key: val for key, val in values.items() if val}
        if values:
            self.partner_id.sudo().write(values)

    def _update_guest_registration_booking(self, product_id, journal_id, immediate_payment, start_date, end_date):
        self.ensure_one()
        sudo_order = self.sudo()
        if start_date and end_date:
            sudo_order.write({"rental_start_date": start_date, "rental_return_date": end_date})

        if product_id:
            line = sudo_order.order_line[:1]
            if line:
                if line.product_id.id != product_id:
                    line.write({"product_id": product_id, "is_rental": True})
            else:
                self.env["sale.order.line"].sudo().create(
                    {
                        "order_id": sudo_order.id,
                        "product_id": product_id,
                        "product_uom_qty": 1,
                        "is_rental": True,
                    }
                )

        if sudo_order.order_line and sudo_order.state == "draft":
            sudo_order.action_confirm()

        if immediate_payment and journal_id and not sudo_order.invoice_ids:
            invoices = sudo_order._create_invoices()
            invoices.action_post()
            payment_register = (
                self.env["account.payment.register"]
                .sudo()
                .with_context(active_model="account.move", active_ids=invoices.ids)
                .create({"journal_id": journal_id})
            )
            payments = payment_register._create_payments()
            payments.action_validate()

        sudo_order._guest_registration_check_in()

    def _guest_registration_check_in(self):
        self.ensure_one()
        if self.state != "sale":
            return
        precision = self.env["decimal.precision"].precision_get("Product Unit")
        lines_to_pickup = self.order_line.filtered(
            lambda line: line.is_rental
            and line.product_type != "combo"
            and float_compare(line.product_uom_qty, line.qty_delivered, precision_digits=precision) > 0
        )
        if not lines_to_pickup:
            return
        wizard_lines = [
            Command.create(self.env["rental.order.wizard.line"]._default_wizard_line_vals(line, "pickup"))
            for line in lines_to_pickup
        ]
        wizard = (
            self.env["rental.order.wizard"]
            .sudo()
            .create({"order_id": self.id, "status": "pickup", "rental_wizard_line_ids": wizard_lines})
        )
        wizard.apply()

    def _update_guest_registration_companions(self, rows):
        """Update existing companion guest lines and create new ones from a submitted form.

        Each row is a dict with ``line_id`` (falsy for a new guest, otherwise the id of
        an existing x_guests_line to update), ``name``, ``is_child`` and an optional
        ``partner_id`` for a new guest already scanned from an ID document, to reuse
        instead of creating a bare partner.
        """
        self.ensure_one()
        sudo_env = self.env(su=True)
        existing_lines = self._get_guest_registration_companions()
        for row in rows:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            is_child = bool(row.get("is_child"))

            line_id = row.get("line_id")
            line = existing_lines.filtered(lambda guest, line_id=line_id: str(guest.id) == line_id)[:1]
            if line:
                line.sudo().x_is_child = is_child
                if line.x_guest_partner_id:
                    line.x_guest_partner_id.sudo().write({"name": name})
                else:
                    line.sudo().x_guest_partner_id = sudo_env["res.partner"].create({"name": name})
                continue

            partner_id = row.get("partner_id")
            if partner_id:
                partner = sudo_env["res.partner"].browse(partner_id)
                partner.write({"name": name})
            else:
                partner = sudo_env["res.partner"].create({"name": name})
            sudo_env["x_guests_line"].create(
                {"x_sale_order_id": self.id, "x_guest_partner_id": partner.id, "x_is_child": is_child}
            )
