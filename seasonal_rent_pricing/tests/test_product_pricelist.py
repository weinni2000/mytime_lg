from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestProductPricelistRentCalendar(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.recurrence_daily = cls.env.ref("sale_renting.recurrence_daily")
        cls.category = cls.env["product.category"].create({"name": "Test Rent Category"})
        cls.product_tmpl = cls.env["product.template"].create(
            {
                "name": "Test Rent Product",
                "type": "consu",
                "rent_ok": True,
                "categ_id": cls.category.id,
                "list_price": 25.0,
            }
        )
        cls.product = cls.product_tmpl.product_variant_id
        cls.pricelist = cls.env["product.pricelist"].create({"name": "Test Pricelist"})
        cls.env["product.pricing"].create(
            {
                "product_template_id": cls.product_tmpl.id,
                "pricelist_id": cls.pricelist.id,
                "recurrence_id": cls.recurrence_daily.id,
                "price": 25.0,
            }
        )
        # A Saturday, matching the weekday rule below.
        cls.saturday = date(2026, 10, 3)

    def _create_weekday_surcharge_rule(self):
        return self.env["product.pricelist.item"].create(
            {
                "pricelist_id": self.pricelist.id,
                "applied_on": "3_global",
                "compute_price": "formula",
                "price_discount": -25.0,
                "price_round": 1,
                "price_surcharge": -0.01,
                "use_weekday_filter": True,
                "weekday_saturday": True,
            }
        )

    def _create_permanent_category_discount_rule(self):
        return self.env["product.pricelist.item"].create(
            {
                "pricelist_id": self.pricelist.id,
                "applied_on": "2_product_category",
                "categ_id": self.category.id,
                "compute_price": "formula",
                "price_discount": 25.0,
                "price_round": 1,
                "price_surcharge": -0.01,
                "date_start": date(2026, 1, 1),
            }
        )

    def test_weekday_surcharge_applies_when_it_is_the_only_rule(self):
        self._create_weekday_surcharge_rule()
        price = self.pricelist._get_rent_calendar_price(self.product, self.saturday)
        self.assertEqual(price, 30.99)

    def test_weekday_surcharge_is_shadowed_by_a_broader_category_rule(self):
        """A permanent, weekday-agnostic category rule outranks a global
        weekday-only rule (product-category rules are more specific than
        global ones), so it wins on every day, including the Saturdays the
        weekday rule targets. This reproduces the pricing seen in production
        where a permanent category discount silently masked the weekend
        surcharge for that category.
        """
        self._create_weekday_surcharge_rule()
        self._create_permanent_category_discount_rule()
        price = self.pricelist._get_rent_calendar_price(self.product, self.saturday)
        self.assertEqual(price, 18.99)

    def test_apply_additionally_layers_on_top_of_the_shadowing_rule(self):
        """Marking the weekday rule ``apply_additionally`` fixes the
        shadowing from the previous test: it no longer competes with the
        category rule for the sole matching-rule slot, and instead re-applies
        its own formula on top of that rule's already-discounted price.
        """
        weekday_rule = self._create_weekday_surcharge_rule()
        weekday_rule.apply_additionally = True
        self._create_permanent_category_discount_rule()
        price = self.pricelist._get_rent_calendar_price(self.product, self.saturday)
        # category rule: 25 * 0.75 -> round(18.75) = 19, - 0.01 = 18.99
        # weekday rule layered on top: 18.99 * 1.25 = 23.7375 -> round = 24, - 0.01 = 23.99
        self.assertEqual(price, 23.99)
