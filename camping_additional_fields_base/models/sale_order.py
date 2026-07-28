from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    special_temporary_info = fields.Text(
        related="company_id.special_temporary_info",
        string="Special Temporary Information",
        readonly=True,
    )
    directions = fields.Text(
        compute="_compute_direction_info",
        string="Directions",
    )
    direction_product_template_ids = fields.Many2many(
        comodel_name="product.template",
        compute="_compute_direction_info",
        string="Source Products",
    )
    is_paid = fields.Boolean(
        string="Paid",
        compute="_compute_is_paid",
        store=True,
    )
    is_ongoing = fields.Boolean(
        string="Ongoing",
        compute="_compute_is_ongoing",
        store=True,
    )

    @api.depends("invoice_ids.payment_state", "invoice_ids.state")
    def _compute_is_paid(self):
        for order in self:
            invoices = order.invoice_ids.filtered(lambda inv: inv.state == "posted")
            order.is_paid = bool(invoices) and all(
                invoice.payment_state in ("paid", "in_payment")
                for invoice in invoices
            )

    @api.depends("rental_start_date", "rental_return_date")
    def _compute_is_ongoing(self):
        now = fields.Datetime.now()
        for order in self:
            order.is_ongoing = bool(
                order.rental_start_date
                and order.rental_return_date
                and order.rental_start_date <= now <= order.rental_return_date
            )

    def _cron_update_is_ongoing(self):
        now = fields.Datetime.now()
        orders = self.search(
            [
                ("rental_start_date", "!=", False),
                ("rental_return_date", "!=", False),
                "|",
                ("is_ongoing", "=", True),
                "&",
                ("rental_start_date", "<=", now),
                ("rental_return_date", ">=", now),
            ]
        )
        orders._compute_is_ongoing()

    @api.depends("order_line.product_id.product_tmpl_id.directions")
    def _compute_direction_info(self):
        for order in self:
            source_products = order.order_line.product_id.product_tmpl_id.filtered(
                "directions"
            )
            directions = source_products.mapped("directions")
            order.directions = "\n\n".join(
                dict.fromkeys(direction.strip() for direction in directions if direction)
            )
            order.direction_product_template_ids = source_products
