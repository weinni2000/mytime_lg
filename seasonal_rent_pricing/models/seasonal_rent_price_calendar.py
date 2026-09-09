from odoo import Command, api, fields, models
from odoo.tools import format_date


class SeasonalRentPriceCalendar(models.TransientModel):
    _name = "seasonal.rent.price.calendar"
    _description = "Rental Price Calendar"

    product_id = fields.Many2one(
        "product.product", string="Product", required=True, domain=[("rent_ok", "=", True)]
    )
    pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Pricelist",
        required=True,
        default=lambda self: self.env["product.pricelist"].search([], limit=1),
    )
    month_date = fields.Date(
        string="Month",
        required=True,
        default=fields.Date.context_today,
        help="Pick any date within the month you want to review.",
    )
    currency_id = fields.Many2one("res.currency", related="pricelist_id.currency_id")
    day_ids = fields.One2many("seasonal.rent.price.calendar.line", "calendar_id", string="Days")

    @api.onchange("product_id", "pricelist_id", "month_date")
    def _onchange_calendar_inputs(self):
        self.day_ids = [Command.clear()]
        if not (self.product_id and self.pricelist_id and self.month_date):
            return
        days = self.env["product.pricelist"]._get_rent_calendar_month_days(self.month_date)
        self.day_ids = [
            Command.create(
                {
                    "date": day,
                    "price": self.pricelist_id._get_rent_calendar_price(self.product_id, day),
                    "currency_id": self.currency_id.id,
                }
            )
            for day in days
        ]


class SeasonalRentPriceCalendarLine(models.TransientModel):
    _name = "seasonal.rent.price.calendar.line"
    _description = "Rental Price Calendar Day"
    _order = "date"

    calendar_id = fields.Many2one("seasonal.rent.price.calendar", ondelete="cascade")
    product_tmpl_id = fields.Many2one("product.template", ondelete="cascade")
    currency_id = fields.Many2one("res.currency")
    date = fields.Date(required=True)
    weekday_label = fields.Char(compute="_compute_weekday_label")
    price = fields.Monetary()

    @api.depends("date")
    def _compute_weekday_label(self):
        for record in self:
            record.weekday_label = format_date(self.env, record.date, date_format="EEEE") if record.date else False
