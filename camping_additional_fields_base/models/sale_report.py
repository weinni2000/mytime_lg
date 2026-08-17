from odoo import fields, models


class SaleReport(models.Model):
    _inherit = "sale.report"

    amount_guests = fields.Integer(
        string="Guests",
        readonly=True,
    )

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        res["amount_guests"] = "s.amount_guests"
        return res

    def _group_by_sale(self):
        res = super()._group_by_sale()
        return f"{res}, s.amount_guests"
