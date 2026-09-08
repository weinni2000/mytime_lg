from odoo import api, fields, models


class GuestRegistrationLinkWizard(models.TransientModel):
    _name = "guest.registration.link.wizard"
    _description = "Guest Registration Link"

    sale_order_id = fields.Many2one("sale.order", required=True, readonly=True)
    url = fields.Char(string="Link", compute="_compute_url")
    partner_email = fields.Char(related="sale_order_id.partner_id.email", readonly=True)

    @api.depends("sale_order_id")
    def _compute_url(self):
        for wizard in self:
            wizard.url = wizard.sale_order_id._get_guest_registration_url()

    def action_send_email(self):
        self.ensure_one()
        self.sale_order_id.action_send_guest_registration_email()
        return {"type": "ir.actions.act_window_close"}
