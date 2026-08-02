from odoo import fields, models

LOCAL_TAX_MIN_AGE = 16


class SaleOrder(models.Model):
    _inherit = "sale.order"

    animal_ids = fields.One2many("animal", "sale_order_id", string="Dogs")

    # pylint: disable=W8110
    def _cart_update_renting_period(self, start_date, end_date):
        """Keep period-dependent camping charges in sync with cart dates."""
        super()._cart_update_renting_period(start_date, end_date)
        for order in self:
            order._update_cart_local_tax_quantity()

    def _update_cart_local_tax_quantity(self):
        self.ensure_one()
        tax_product = self.company_id.x_local_tax_product_id
        if not tax_product:
            return

        adult_guest_count = len(
            self.x_guest_line_ids.filtered(lambda guest: guest.x_guest_age >= LOCAL_TAX_MIN_AGE)
        )
        nights = 0
        if self.rental_start_date and self.rental_return_date:
            nights = (self.rental_return_date.date() - self.rental_start_date.date()).days

        tax_line = self._cart_find_product_line(tax_product.id, uom_id=tax_product.uom_id.id)[:1]
        quantity = adult_guest_count * max(nights, 0)
        if tax_line:
            self._cart_update_line_quantity(line_id=tax_line.id, quantity=quantity)
        elif quantity:
            self._cart_add(product_id=tax_product.id, quantity=quantity)
