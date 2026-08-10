from odoo import _, api, fields, models
from odoo.tools.float_utils import float_compare


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def action_checkout_expired_rentals(self):
        orders = self.search(
            [
                ("state", "=", "sale"),
                ("rental_status", "=", "return"),
                ("rental_return_date", "<", fields.Datetime.now()),
            ]
        )
        precision = self.env["decimal.precision"].precision_get("Product Unit")
        checkout_count = 0

        for order in orders:
            lines = order.order_line.filtered(
                lambda line: line.is_rental
                and line.product_type != "combo"
                and float_compare(
                    line.qty_delivered,
                    line.qty_returned,
                    precision_digits=precision,
                )
                > 0
            )
            if not lines:
                continue

            wizard_lines = [
                (
                    0,
                    0,
                    self.env["rental.order.wizard.line"]._default_wizard_line_vals(line, "return"),
                )
                for line in lines
            ]
            wizard = self.env["rental.order.wizard"].create(
                {
                    "order_id": order.id,
                    "status": "return",
                    "rental_wizard_line_ids": wizard_lines,
                }
            )
            wizard.apply()
            checkout_count += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Checkout complete"),
                "message": _("Checked out %(count)s expired booking(s).", count=checkout_count),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }
