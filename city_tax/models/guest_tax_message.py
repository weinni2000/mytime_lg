from odoo import api, fields, models


class GuestTaxMessage(models.Model):
    _name = "guest.tax.message"
    _description = "Guest Tax Message"
    _inherit = ["guest.tax.deskline.mixin"]

    name = fields.Char(required=True, copy=False, readonly=True, default="/")
    x_sale_order_id = fields.Many2one("sale.order", string="Sale Order")
    x_guest_line_ids = fields.One2many("y_guests_line", "x_group_id", string="Guests")
    x_arrival_date = fields.Date(
        string="Arrival",
        help="Check-in date for the whole stay — used by all guests in this "
        "message unless a guest has its own manual override.",
    )
    x_departure_date = fields.Date(
        string="Departure",
        help="Check-out date for the whole stay — used by all guests in this "
        "message unless a guest has its own manual override.",
    )

    _name_uniq = models.Constraint("unique(name)", "This grouping already exists.")

    @api.model
    def _get_or_create_for_sale_order(self, sale_order):
        message = self.search([("x_sale_order_id", "=", sale_order.id)], limit=1)
        if not message:
            message = self.create({"name": sale_order.name, "x_sale_order_id": sale_order.id})
        return message

    @api.model
    def _create_standalone(self):
        name = self.env["ir.sequence"].next_by_code("y_guests_line.group")
        return self.create({"name": name})

    def _get_deskline_guest_lines(self):
        self.ensure_one()
        return self.x_guest_line_ids

    def _get_deskline_company(self):
        self.ensure_one()
        return self.x_sale_order_id.company_id or self.env.company
