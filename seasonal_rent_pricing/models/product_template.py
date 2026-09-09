from odoo import Command, api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    rent_calendar_pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Pricelist",
        default=lambda self: self.env["product.pricelist"].search([], limit=1),
    )
    rent_calendar_month = fields.Date(string="Month", default=fields.Date.context_today)
    rent_calendar_day_ids = fields.One2many(
        "seasonal.rent.price.calendar.line",
        "product_tmpl_id",
        string="Days",
        compute="_compute_rent_calendar_day_ids",
    )

    @api.depends("rent_calendar_pricelist_id", "rent_calendar_month", "rent_ok", "product_variant_id")
    def _compute_rent_calendar_day_ids(self):
        for record in self:
            record.rent_calendar_day_ids = [Command.clear()]
            pricelist = record.rent_calendar_pricelist_id
            product = record.product_variant_id
            if not (record.rent_ok and pricelist and record.rent_calendar_month and product):
                continue
            days = self.env["product.pricelist"]._get_rent_calendar_month_days(record.rent_calendar_month)
            record.rent_calendar_day_ids = [
                Command.create(
                    {
                        "date": day,
                        "price": pricelist._get_rent_calendar_price(product, day),
                        "currency_id": pricelist.currency_id.id,
                    }
                )
                for day in days
            ]
