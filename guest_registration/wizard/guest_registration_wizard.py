from datetime import timedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class GuestRegistrationWizard(models.TransientModel):
    _name = "guest.registration.wizard"
    _description = "Guest Registration"

    sale_order_id = fields.Many2one("sale.order", required=True, readonly=True, ondelete="cascade")
    url = fields.Char(string="Web Form Link", compute="_compute_url")

    id_document_front = fields.Image(string="Document Front")
    id_document_back = fields.Image(string="Document Back")

    rental_start_date = fields.Datetime(string="Start Date")
    rental_return_date = fields.Datetime(string="End Date")
    product_id = fields.Many2one(
        "product.product", string="Product", domain=[("product_tmpl_id.x_is_a_room_offer", "=", True)]
    )
    immediate_payment = fields.Boolean(string="Already Paid")
    journal_id = fields.Many2one(
        "account.journal", string="Payment Journal", domain=[("type", "in", ("bank", "cash"))]
    )
    booking_details_warning = fields.Char(compute="_compute_booking_details_warning")

    name = fields.Char()
    birthdate_date = fields.Date(string="Birthdate")
    location_id = fields.Many2one("res.city.zip", string="Search Address (ZIP or City)")
    street = fields.Char()
    zip = fields.Char()
    city = fields.Char()
    country_id = fields.Many2one("res.country", string="Country")
    nationality_id = fields.Many2one("res.country", string="Nationality")
    email = fields.Char()
    phone = fields.Char()

    guest_line_ids = fields.One2many("guest.registration.wizard.line", "wizard_id", string="Other Guests")

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        order_id = vals.get("sale_order_id") or self.env.context.get("default_sale_order_id")
        if not order_id:
            return vals

        order = self.env["sale.order"].browse(order_id)
        partner = order.partner_id
        today = fields.Date.context_today(self)
        vals.update(
            {
                "sale_order_id": order.id,
                "name": partner.name or "",
                "birthdate_date": partner.birthdate_date,
                "street": partner.street,
                "zip": partner.zip,
                "city": partner.city,
                "country_id": partner.country_id.id,
                "email": partner.email,
                "phone": partner.phone,
                "rental_start_date": order.rental_start_date or fields.Datetime.to_datetime(today),
                "rental_return_date": order.rental_return_date
                or fields.Datetime.to_datetime(today + timedelta(days=1)),
                "product_id": order.order_line[:1].product_id.id,
                "immediate_payment": order.is_paid,
                "journal_id": order.invoice_ids.matched_payment_ids.journal_id[:1].id,
                "guest_line_ids": [
                    Command.create(
                        {
                            "guest_line_id": guest.id,
                            "name": guest.x_guest_partner_id.name or "",
                            "is_child": guest.x_is_child,
                        }
                    )
                    for guest in order._get_guest_registration_companions()
                ],
            }
        )
        return vals

    @api.depends("rental_start_date", "rental_return_date", "product_id", "immediate_payment", "journal_id")
    def _compute_booking_details_warning(self):
        for wizard in self:
            missing = []
            if not wizard.rental_start_date:
                missing.append(wizard.env._("Start Date"))
            if not wizard.rental_return_date:
                missing.append(wizard.env._("End Date"))
            if not wizard.product_id:
                missing.append(wizard.env._("Product"))
            if wizard.immediate_payment and not wizard.journal_id:
                missing.append(wizard.env._("Payment Journal"))
            if missing:
                message = wizard.env._("Missing booking details: %(fields)s")
                wizard.booking_details_warning = message % {"fields": ", ".join(missing)}
            else:
                wizard.booking_details_warning = False

    @api.onchange("location_id")
    def _onchange_location_id(self):
        if self.location_id:
            self.zip = self.location_id.name
            self.city = self.location_id.city_id.name
            self.country_id = self.location_id.city_id.country_id

    @api.depends("sale_order_id")
    def _compute_url(self):
        for wizard in self:
            wizard.url = wizard.sale_order_id._get_guest_registration_url() if wizard.sale_order_id else False

    def action_open_web_form(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": self.url, "target": "new"}

    def action_open_guest_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "guest.registration.guest.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_wizard_id": self.id},
        }

    def action_scan_id_documents(self):
        self.ensure_one()
        if not self.id_document_front and not self.id_document_back:
            raise UserError(_("Upload a front or back image of the document first."))

        partner_sudo = self.sale_order_id.partner_id.sudo()
        scan_values = {}
        if self.id_document_front:
            scan_values["x_id_document_front"] = self.id_document_front
        if self.id_document_back:
            scan_values["x_id_document_back"] = self.id_document_back
        partner_sudo.write(scan_values)
        partner_sudo.action_scan_id_documents()

        self.write(
            {
                key: val
                for key, val in {
                    "name": partner_sudo.name,
                    "birthdate_date": partner_sudo.birthdate_date,
                    "street": partner_sudo.street,
                    "zip": partner_sudo.zip,
                    "city": partner_sudo.city,
                    "country_id": partner_sudo.country_id.id,
                    "nationality_id": partner_sudo.x_nationality.id,
                }.items()
                if val
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_confirm(self):
        self.ensure_one()
        if self.booking_details_warning:
            raise UserError(self.booking_details_warning)

        order = self.sale_order_id
        order._update_guest_registration_address(
            {
                "name": self.name,
                "street": self.street,
                "zip": self.zip,
                "city": self.city,
                "country_id": self.country_id.id,
                "x_nationality": self.nationality_id.id,
                "phone": self.phone,
                "email": self.email,
                "birthdate_date": self.birthdate_date,
            }
        )

        rows = [
            {
                "line_id": str(line.guest_line_id.id) if line.guest_line_id else "",
                "name": line.name,
                "is_child": line.is_child,
                "partner_id": line.guest_partner_id.id,
            }
            for line in self.guest_line_ids
        ]
        order._update_guest_registration_companions(rows)

        order._update_guest_registration_booking(
            self.product_id.id,
            self.journal_id.id if self.immediate_payment else False,
            self.immediate_payment,
            self.rental_start_date,
            self.rental_return_date,
        )
        return {"type": "ir.actions.act_window_close"}


class GuestRegistrationWizardLine(models.TransientModel):
    _name = "guest.registration.wizard.line"
    _description = "Guest Registration Wizard Line"

    wizard_id = fields.Many2one("guest.registration.wizard", required=True, ondelete="cascade")
    guest_line_id = fields.Many2one("x_guests_line", readonly=True)
    guest_partner_id = fields.Many2one("res.partner", readonly=True)
    name = fields.Char(string="Guest Name")
    is_child = fields.Boolean(string="Child")
