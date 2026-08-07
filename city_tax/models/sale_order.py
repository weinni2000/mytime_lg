from odoo import api, fields, models


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "guest.tax.deskline.mixin"]

    x_transferred_to_deskline = fields.Boolean(
        string="Transferred to Deskline", compute="_compute_x_transferred_to_deskline", store=True
    )
    x_data_valid = fields.Boolean(string="Data Valid", compute="_compute_x_data_valid", store=True)

    refresh = fields.Boolean(help="Toggle to force the computed Data Valid to recompute.")

    @api.depends("x_deskline_master_id")
    def _compute_x_transferred_to_deskline(self):
        for order in self:
            order.x_transferred_to_deskline = bool(order.x_deskline_master_id)

    @api.depends(
        "x_guest_line_ids.x_main_guest",
        "x_guest_line_ids.x_main_guest_check",
        "x_guest_line_ids.x_tourist_tax_check",
        "refresh",
    )
    def _compute_x_data_valid(self):
        for order in self:
            order.x_data_valid = any(guest_line.x_main_guest for guest_line in order.x_guest_line_ids) and all(
                guest_line.x_main_guest_check == "ok" and guest_line.x_tourist_tax_check == "ok"
                for guest_line in order.x_guest_line_ids
            )

    def create(self, vals_list):
        orders = super().create(vals_list)
        # Guard against reentrancy: _add_partner_as_guest assigning
        # x_guest_line_ids below triggers another write() on these same
        # records, which would otherwise call it again.
        for order in orders.with_context(_skip_add_partner_as_guest=True):
            order._add_partner_as_guest()
        return orders

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("_skip_add_partner_as_guest"):
            for order in self.with_context(_skip_add_partner_as_guest=True):
                order._add_partner_as_guest()
        return res

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
