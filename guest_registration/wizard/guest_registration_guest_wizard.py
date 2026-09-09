from odoo import Command, _, fields, models
from odoo.exceptions import UserError


class GuestRegistrationGuestWizard(models.TransientModel):
    _name = "guest.registration.guest.wizard"
    _description = "Add Guest via ID Scan"

    wizard_id = fields.Many2one("guest.registration.wizard", required=True, ondelete="cascade")
    guest_partner_id = fields.Many2one("res.partner", readonly=True)

    id_document_front = fields.Image(string="Document Front")
    id_document_back = fields.Image(string="Document Back")
    name = fields.Char()
    is_child = fields.Boolean(string="Child")
    birthdate_date = fields.Date(string="Birthdate")
    street = fields.Char()
    zip = fields.Char()
    city = fields.Char()
    country_id = fields.Many2one("res.country", string="Country")
    nationality_id = fields.Many2one("res.country", string="Nationality")

    def action_scan_id_documents(self):
        self.ensure_one()
        if not self.id_document_front and not self.id_document_back:
            raise UserError(_("Upload a front or back image of the document first."))

        partner = self.guest_partner_id
        if not partner:
            partner = self.env["res.partner"].create({"name": _("New Guest")})
            self.guest_partner_id = partner.id

        scan_values = {}
        if self.id_document_front:
            scan_values["x_id_document_front"] = self.id_document_front
        if self.id_document_back:
            scan_values["x_id_document_back"] = self.id_document_back
        partner.write(scan_values)
        partner.action_scan_id_documents()
        self.write(
            {
                key: val
                for key, val in {
                    "name": partner.name,
                    "birthdate_date": partner.birthdate_date,
                    "street": partner.street,
                    "zip": partner.zip,
                    "city": partner.city,
                    "country_id": partner.country_id.id,
                    "nationality_id": partner.x_nationality.id,
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

    def action_add_guest(self):
        self.ensure_one()
        name = (self.name or "").strip()
        if not name:
            raise UserError(_("Enter the guest's name first."))

        if self.guest_partner_id:
            self.guest_partner_id.write(
                {
                    key: val
                    for key, val in {
                        "name": name,
                        "birthdate_date": self.birthdate_date,
                        "street": self.street,
                        "zip": self.zip,
                        "city": self.city,
                        "country_id": self.country_id.id,
                        "x_nationality": self.nationality_id.id,
                    }.items()
                    if val
                }
            )

        self.wizard_id.guest_line_ids = [
            Command.create(
                {
                    "name": name,
                    "is_child": self.is_child,
                    "guest_partner_id": self.guest_partner_id.id,
                }
            )
        ]
        # Reopen the parent wizard explicitly instead of act_window_close,
        # which closes the whole stacked "new"-target dialogs.
        return {
            "type": "ir.actions.act_window",
            "res_model": self.wizard_id._name,
            "res_id": self.wizard_id.id,
            "view_mode": "form",
            "target": "new",
        }
