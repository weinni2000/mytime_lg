from odoo import api, fields, models


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "guest.tax.deskline.mixin"]

    y_guest_line_ids = fields.One2many("y_guests_line", "x_sale_order_id", string="Guests (Y)")

    def action_add_partner_as_guest(self):
        for order in self:
            order._add_partner_as_guest()

    @api.onchange("partner_id")
    def _onchange_partner_id_add_guest(self):
        for order in self:
            order._add_partner_as_guest()

    def _add_partner_as_guest(self):
        self.ensure_one()
        if not self.partner_id:
            return
        existing = self.x_guest_line_ids.filtered(
            lambda guest_line: guest_line.x_guest_partner_id == self.partner_id
        )
        if existing:
            existing.x_main_guest = True
        else:
            self.x_guest_line_ids = [
                (
                    0,
                    0,
                    {
                        "x_guest_partner_id": self.partner_id.id,
                        "x_main_guest": True,
                    },
                )
            ]

    def _get_deskline_guest_lines(self):
        self.ensure_one()
        return self.x_guest_line_ids

    def _get_deskline_company(self):
        self.ensure_one()
        return self.company_id
