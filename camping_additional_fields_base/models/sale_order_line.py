from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._camping_force_rental_line(vals)
        return super().create(vals_list)

    @api.model
    def _camping_force_rental_line(self, vals):
        # Adding a rentable product to a rental order through the plain "Add a
        # product" line creates it with is_rental=False. A non-rental line on a
        # (confirmed) rental order makes Odoo's planning slot-sync write that
        # line's empty, header-related start_date/return_date back onto the
        # shared sale.order.rental_start_date/rental_return_date, wiping the
        # rental period for *every* line and leaving a dateless planning slot.
        # That breaks the booking and later crashes cancellation on
        # localized(False). Rentable products on a rental order must therefore
        # be rental lines so they share the header dates instead of clearing
        # them.
        if vals.get("is_rental"):
            return
        order_id = vals.get("order_id")
        product_id = vals.get("product_id")
        if not order_id or not product_id:
            return
        order = self.env["sale.order"].browse(order_id)
        product = self.env["product.product"].browse(product_id)
        if order.is_rental_order and product.rent_ok:
            vals["is_rental"] = True

    @api.onchange("product_id")
    def _onchange_product_id_camping_force_rental(self):
        # Mirror the create() guard in the form UI so the user immediately sees
        # the line marked as a rental line when picking a rentable product on a
        # rental order.
        for line in self:
            if line.order_id.is_rental_order and line.product_id.rent_ok and not line.is_rental:
                line.is_rental = True
