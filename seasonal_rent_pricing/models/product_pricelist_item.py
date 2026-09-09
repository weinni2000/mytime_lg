from odoo import _, api, fields, models
from odoo.tools import float_round, format_datetime

_WEEKDAY_FIELDS = [
    "weekday_monday",
    "weekday_tuesday",
    "weekday_wednesday",
    "weekday_thursday",
    "weekday_friday",
    "weekday_saturday",
    "weekday_sunday",
]
_WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTH_FIELDS = [
    "month_january",
    "month_february",
    "month_march",
    "month_april",
    "month_may",
    "month_june",
    "month_july",
    "month_august",
    "month_september",
    "month_october",
    "month_november",
    "month_december",
]
_MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class ProductPricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    use_weekday_filter = fields.Boolean(string="Use Weekdays")
    weekday_monday = fields.Boolean(string="Mon")
    weekday_tuesday = fields.Boolean(string="Tue")
    weekday_wednesday = fields.Boolean(string="Wed")
    weekday_thursday = fields.Boolean(string="Thu")
    weekday_friday = fields.Boolean(string="Fri")
    weekday_saturday = fields.Boolean(string="Sat")
    weekday_sunday = fields.Boolean(string="Sun")
    weekday_summary = fields.Char(string="Weekdays", compute="_compute_weekday_summary")
    use_month_filter = fields.Boolean(string="Use Months")
    month_january = fields.Boolean(string="Jan")
    month_february = fields.Boolean(string="Feb")
    month_march = fields.Boolean(string="Mar")
    month_april = fields.Boolean(string="Apr")
    month_may = fields.Boolean(string="May")
    month_june = fields.Boolean(string="Jun")
    month_july = fields.Boolean(string="Jul")
    month_august = fields.Boolean(string="Aug")
    month_september = fields.Boolean(string="Sep")
    month_october = fields.Boolean(string="Oct")
    month_november = fields.Boolean(string="Nov")
    month_december = fields.Boolean(string="Dec")
    month_summary = fields.Char(string="Months", compute="_compute_month_summary")
    apply_additionally = fields.Boolean(
        help=(
            "Layer this rule's adjustment on top of whichever other rule "
            "already applies for a given day, instead of competing with it "
            "to be the sole matching rule. Use this so a more specific rule "
            "(e.g. a permanent category discount) doesn't silently shadow "
            "this one (e.g. a weekend surcharge)."
        ),
    )
    validity_summary = fields.Char(string="Validity", compute="_compute_validity_summary")

    @api.depends("use_weekday_filter", *_WEEKDAY_FIELDS)
    def _compute_weekday_summary(self):
        for record in self:
            selected = [
                label
                for field_name, label in zip(_WEEKDAY_FIELDS, _WEEKDAY_LABELS, strict=False)
                if record[field_name]
            ]
            record.weekday_summary = ", ".join(selected) if record.use_weekday_filter and selected else False

    @api.depends("use_month_filter", *_MONTH_FIELDS)
    def _compute_month_summary(self):
        for record in self:
            selected = [
                label
                for field_name, label in zip(_MONTH_FIELDS, _MONTH_LABELS, strict=False)
                if record[field_name]
            ]
            record.month_summary = ", ".join(selected) if record.use_month_filter and selected else False

    @api.depends(
        "date_start",
        "date_end",
        "use_weekday_filter",
        "use_month_filter",
        "apply_additionally",
        "weekday_summary",
        "month_summary",
    )
    def _compute_validity_summary(self):
        for record in self:
            if record.use_weekday_filter or record.use_month_filter:
                parts = [part for part in (record.weekday_summary, record.month_summary) if part]
                summary = " / ".join(parts) if parts else _("Every day")
            elif record.date_start or record.date_end:
                start = (
                    format_datetime(self.env, record.date_start, dt_format="short") if record.date_start else "…"
                )
                end = format_datetime(self.env, record.date_end, dt_format="short") if record.date_end else "…"
                summary = f"{start} → {end}"
            else:
                summary = False
            if summary and record.apply_additionally:
                summary = _("%(summary)s (additional)") % {"summary": summary}
            record.validity_summary = summary

    @api.onchange("use_weekday_filter", "use_month_filter")
    def _onchange_use_pattern_filter(self):
        if self.use_weekday_filter or self.use_month_filter:
            self.date_start = False
            self.date_end = False
        if not self.use_weekday_filter:
            for field_name in _WEEKDAY_FIELDS:
                self[field_name] = False
        if not self.use_month_filter:
            for field_name in _MONTH_FIELDS:
                self[field_name] = False

    def _matches_weekday(self, day):
        """Whether this rule applies on ``day``'s weekday.

        With no weekday checked the rule applies every day, matching the
        previous (weekday-agnostic) behaviour.
        """
        self.ensure_one()
        active_fields = [field_name for field_name in _WEEKDAY_FIELDS if self[field_name]]
        if not active_fields:
            return True
        return self[_WEEKDAY_FIELDS[day.weekday()]]

    def _matches_month(self, day):
        """Whether this rule applies on ``day``'s month.

        With no month checked the rule applies in every month, matching the
        previous (month-agnostic) behaviour.
        """
        self.ensure_one()
        active_fields = [field_name for field_name in _MONTH_FIELDS if self[field_name]]
        if not active_fields:
            return True
        return self[_MONTH_FIELDS[day.month - 1]]

    def _apply_additional_price(self, price):
        """Re-apply this rule's own formula on top of ``price``.

        Unlike ``_compute_price``, this does not derive its own base price
        (list price, other pricelist, ...); it treats ``price`` (the price
        already produced by whichever other rule matched that day) as the
        base to adjust, so an ``apply_additionally`` rule layers on top
        instead of competing to be the sole matching rule.
        """
        self.ensure_one()
        if self.compute_price == "fixed":
            return self.fixed_price
        if self.compute_price == "percentage":
            return (price - (price * (self.percent_price / 100))) or 0.0
        if self.compute_price == "formula":
            discount = self.price_discount if self.base != "standard_price" else -self.price_markup
            new_price = price - (price * (discount / 100))
            if self.price_round:
                new_price = float_round(new_price, precision_rounding=self.price_round)
            if self.price_surcharge:
                new_price += self.price_surcharge
            if self.price_min_margin:
                new_price = max(new_price, price + self.price_min_margin)
            if self.price_max_margin:
                new_price = min(new_price, price + self.price_max_margin)
            return new_price
        return price
