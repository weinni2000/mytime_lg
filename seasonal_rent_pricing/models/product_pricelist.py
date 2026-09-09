import calendar
from datetime import timedelta

from odoo import api, fields, models


class ProductPricelist(models.Model):
    _inherit = "product.pricelist"

    def _compute_price_rule(
        self,
        products,
        quantity,
        *,
        currency=None,
        uom=None,
        date=False,
        compute_price=True,
        start_date=None,
        end_date=None,
        **kwargs,
    ):
        """Apply pricelist discount rules to rental lines, per day.

        ``sale_renting`` prices rental products purely from ``product.pricing``
        rules and never looks at the pricelist discount/formula items (see
        ``sale_renting/models/product_pricelist.py`` and
        ``sale_order_line._compute_pricelist_item_id``).

        This override keeps that rental base price, then walks every day of the
        rental period: on days whose date matches an applicable pricelist item
        (a seasonal discount rule) the item's own computed price is used for
        that day, so the full formula is honoured (discount, price rounding and
        surcharge); the remaining days keep the rental base price. A stay
        straddling the season boundary is therefore only discounted for the
        days inside the window.

        Note: the item price is taken per day, which assumes a per-day / per-
        night rental pricing (the ``product.pricing`` price is a nightly rate).
        This matches the camping use case; it is not meant for flat-period
        (weekly/monthly) rental pricings.
        """
        results = super()._compute_price_rule(
            products,
            quantity,
            currency=currency,
            uom=uom,
            date=date,
            compute_price=compute_price,
            start_date=start_date,
            end_date=end_date,
            **kwargs,
        )
        if not (
            self and compute_price and start_date and end_date and self._enable_rental_price(start_date, end_date)
        ):
            return results

        currency = currency or self.currency_id or self.env.company.currency_id
        for product in products.filtered("rent_ok"):
            res = results.get(product.id)
            if not res:
                continue
            base_price, rule_id = res
            new_price = self._seasonal_rental_unit_price(
                product, quantity, uom, base_price, currency, start_date, end_date
            )
            if new_price is not None:
                results[product.id] = (new_price, rule_id)
        return results

    def _seasonal_rental_days(self, start_date, end_date):
        """Return one datetime per rental day, aligned with the rental duration.

        Uses the same day count as the rental engine
        (``product.pricing._compute_duration_vals``) so that the sum of the
        per-day prices matches the full rental base price.
        """
        start_dt = fields.Datetime.to_datetime(start_date)
        end_dt = fields.Datetime.to_datetime(end_date)
        vals = self.env["product.pricing"]._compute_duration_vals(start_dt, end_dt)
        num_days = max(int(vals.get("day") or 0), 1)
        return [start_dt + timedelta(days=index) for index in range(num_days)]

    def _seasonal_qty_in_product_uom(self, product, quantity, uom):
        product_uom = product.uom_id
        if uom and uom != product_uom:
            return uom._compute_quantity(quantity, product_uom, raise_if_failure=False)
        return quantity

    def _seasonal_suitable_item(self, product, quantity, uom, date):
        """First non-additional pricelist item applicable to ``product`` on ``date``.

        Mirrors the suitable-rule selection of the core
        ``_compute_price_rule`` but scoped to a single date, so each rental day
        is matched against the item date window independently. A rule with one
        or more weekdays checked only matches days that fall on one of those
        weekdays; a rule with none checked matches every day in its window.
        The same applies to the rule's checked months, if any. Rules marked
        ``apply_additionally`` are skipped here; see
        ``_seasonal_additional_items``.
        """
        self.ensure_one()
        rules = self._get_applicable_rules(product, date)
        qty_in_product_uom = self._seasonal_qty_in_product_uom(product, quantity, uom)
        for rule in rules:
            if (
                not rule.apply_additionally
                and rule._is_applicable_for(product, qty_in_product_uom)
                and rule._matches_weekday(date)
                and rule._matches_month(date)
            ):
                return rule
        return self.env["product.pricelist.item"]

    def _seasonal_additional_items(self, product, quantity, uom, date):
        """All ``apply_additionally`` pricelist items applicable to ``product`` on ``date``.

        These are layered on top of whatever price
        ``_seasonal_suitable_item`` (or the plain rental base price) already
        produced for that day, instead of competing to be the sole matching
        rule - so a more specific rule (e.g. a permanent category discount)
        can't silently shadow one of these (e.g. a weekend surcharge).
        """
        self.ensure_one()
        rules = self._get_applicable_rules(product, date)
        qty_in_product_uom = self._seasonal_qty_in_product_uom(product, quantity, uom)
        return rules.filtered(
            lambda rule: rule.apply_additionally
            and rule._is_applicable_for(product, qty_in_product_uom)
            and rule._matches_weekday(date)
            and rule._matches_month(date)
        )

    def _seasonal_rental_unit_price(self, product, quantity, uom, base_price, currency, start_date, end_date):
        """Blend the rental base price with per-day pricelist discounts.

        Each day whose date matches a pricelist item is priced with that item's
        own computed price (honouring the full formula: discount, rounding and
        surcharge). Days without a matching item keep their share of the rental
        base price. Any ``apply_additionally`` items matching that day are then
        layered on top of that day's price.

        :returns: the adjusted unit price, or ``None`` when no rental day
                  matches a pricelist item (base price is then left untouched).
        """
        self.ensure_one()
        target_uom = uom or product.uom_id
        days = self._seasonal_rental_days(start_date, end_date)
        per_day_price = base_price / len(days)
        total = 0.0
        matched = False
        for day in days:
            item = self._seasonal_suitable_item(product, quantity, target_uom, day)
            if item:
                day_price = item._compute_price(product, quantity, target_uom, day, currency=currency)
                matched = True
            else:
                day_price = per_day_price
            additional_items = self._seasonal_additional_items(product, quantity, target_uom, day)
            for additional_item in additional_items:
                day_price = additional_item._apply_additional_price(day_price)
                matched = True
            total += day_price
        return total if matched else None

    @api.model
    def _get_rent_calendar_month_days(self, month_date):
        """Return one date per day of the month containing ``month_date``."""
        first_day = month_date.replace(day=1)
        _weekday, days_in_month = calendar.monthrange(first_day.year, first_day.month)
        return [first_day + timedelta(days=offset) for offset in range(days_in_month)]

    def _get_rent_calendar_price(self, product, day):
        """Price ``product`` would be rented at for the single night ``day``."""
        self.ensure_one()
        start = fields.Datetime.to_datetime(day)
        end = start + timedelta(days=1)
        results = self._compute_price_rule(product, 1, start_date=start, end_date=end, date=start)
        price, _rule_id = results.get(product.id, (0.0, False))
        return price
