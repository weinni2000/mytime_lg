from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestProductPricelistItemWeekdayMonthFilter(TransactionCase):
    def test_matches_weekday_none_checked_matches_every_day(self):
        item = self.env["product.pricelist.item"].new({})
        for day in range(7):
            self.assertTrue(item._matches_weekday(date(2026, 10, 4 + day)))

    def test_matches_weekday_only_checked_days(self):
        item = self.env["product.pricelist.item"].new({"weekday_friday": True, "weekday_saturday": True})
        self.assertTrue(item._matches_weekday(date(2026, 10, 2)))  # Friday
        self.assertTrue(item._matches_weekday(date(2026, 10, 3)))  # Saturday
        self.assertFalse(item._matches_weekday(date(2026, 10, 4)))  # Sunday
        self.assertFalse(item._matches_weekday(date(2026, 10, 1)))  # Thursday

    def test_matches_month_none_checked_matches_every_month(self):
        item = self.env["product.pricelist.item"].new({})
        self.assertTrue(item._matches_month(date(2026, 1, 15)))
        self.assertTrue(item._matches_month(date(2026, 12, 15)))

    def test_matches_month_only_checked_months(self):
        item = self.env["product.pricelist.item"].new({"month_july": True, "month_august": True})
        self.assertTrue(item._matches_month(date(2026, 7, 1)))
        self.assertTrue(item._matches_month(date(2026, 8, 31)))
        self.assertFalse(item._matches_month(date(2026, 6, 30)))
        self.assertFalse(item._matches_month(date(2026, 9, 1)))

    def test_onchange_switches_between_dates_and_weekdays(self):
        item = self.env["product.pricelist.item"].new(
            {"date_start": date(2026, 1, 1), "date_end": date(2026, 12, 31)}
        )
        item.use_weekday_filter = True
        item._onchange_use_pattern_filter()
        self.assertFalse(item.date_start)
        self.assertFalse(item.date_end)

        item.weekday_saturday = True
        item.use_weekday_filter = False
        item._onchange_use_pattern_filter()
        self.assertFalse(item.weekday_saturday)
