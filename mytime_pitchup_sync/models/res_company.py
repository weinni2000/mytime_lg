import logging
import re
from datetime import datetime, time
from decimal import Decimal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PITCHUP_API_ROOT = "https://www.pitchup.com/rest/api"
PITCHUP_TIMEOUT = 30
VIENNA = ZoneInfo("Europe/Vienna")
UTC = ZoneInfo("UTC")


class ResCompany(models.Model):
    _inherit = "res.company"

    pitchup_api_key = fields.Char(
        string="Pitchup API Key",
        copy=False,
        groups="base.group_system",
    )

    def _pitchup_get(self, path, params=None):
        self.ensure_one()
        url = path if path.startswith("http") else f"{PITCHUP_API_ROOT}{path}"
        response = requests.get(
            url,
            params=params,
            headers={
                "Authorization": f"Token {self.pitchup_api_key}",
                "User-Agent": "mytime_pitchup_sync/19.0",
            },
            timeout=PITCHUP_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def _pitchup_fetch_bookings(self):
        self.ensure_one()
        data = self._pitchup_get("/booking/", {"page_size": 100})
        bookings = []
        while True:
            bookings.extend(data.get("results", []))
            next_url = data.get("next")
            if not next_url:
                return bookings
            data = self._pitchup_get(next_url)

    @staticmethod
    def _pitchup_id_from_url(value):
        path = urlparse(value or "").path.rstrip("/")
        try:
            return int(path.rsplit("/", 1)[-1])
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _pitchup_money(booking, field_name="price"):
        value = booking.get(field_name) or {}
        return float(Decimal(str(value.get("amount") or "0")))

    @staticmethod
    def _pitchup_utc_datetime(date_value, local_time):
        local = datetime.combine(fields.Date.to_date(date_value), local_time, tzinfo=VIENNA)
        return local.astimezone(UTC).replace(tzinfo=None)

    @staticmethod
    def _phone_digits(phone):
        return re.sub(r"\D", "", phone or "")

    def _pitchup_find_partner(self, booking):
        partner_model = self.env["res.partner"].sudo()
        email = (booking.get("email") or "").strip()
        if email:
            partner = partner_model.search([("email", "=ilike", email)], limit=1)
            if partner:
                return partner

        phone = booking.get("telephone") or ""
        digits = self._phone_digits(phone)
        if len(digits) >= 7:
            tail = digits[-9:]
            candidates = partner_model.search([("phone", "like", tail)])
            partner = next(
                (item for item in candidates if self._phone_digits(item.phone).endswith(tail)),
                partner_model,
            )
            if partner:
                return partner

        name = " ".join(filter(None, [booking.get("first_name"), booking.get("last_name")])).strip() or _(
            "Pitchup guest"
        )
        return partner_model.create(
            {
                "name": name,
                "email": email,
                "phone": phone,
            }
        )

    def _pitchup_sale_channel(self):
        self.ensure_one()
        channel_model = self.env["sale.channel"].sudo()
        channel = channel_model.search(
            [
                ("name", "=ilike", "Pitchup"),
                ("company_id", "in", [False, self.id]),
            ],
            limit=1,
        )
        return channel or channel_model.create(
            {
                "name": "Pitchup",
                "company_id": self.id,
            }
        )

    def _pitchup_order_values(self, booking, partner, channel, product):
        arrive = booking["arrive"]
        depart = booking["depart"]
        booking_id = booking.get("pretty_id") or str(booking["id"])
        adults = booking.get("adults") or 0
        children = booking.get("children") or 0
        infants = booking.get("infants") or 0
        price = self._pitchup_money(booking)
        deposit = self._pitchup_money(booking, "deposit")
        remainder = self._pitchup_money(booking, "remainder")
        note = "\n".join(
            [
                "Imported from Pitchup API",
                f"Pitchup booking ID: {booking_id}",
                f"Status: {booking.get('status') or ''}",
                f"Adults: {adults}",
                f"Children: {children}",
                f"Infants: {infants}",
                f"Deposit: {deposit:.2f}",
                f"Remainder: {remainder:.2f}",
                f"Special requests: {booking.get('special_requests') or ''}",
            ]
        )
        line_name = f"{product.display_name}\n{arrive} 18:00 to {depart} 09:00"
        return {
            "partner_id": partner.id,
            "partner_invoice_id": partner.id,
            "partner_shipping_id": partner.id,
            "company_id": self.id,
            "sale_channel_id": channel.id,
            "origin": "Pitchup API",
            "client_order_ref": booking_id,
            "note": note,
            "is_rental_order": True,
            "rental_start_date": self._pitchup_utc_datetime(arrive, time(18, 0)),
            "rental_return_date": self._pitchup_utc_datetime(depart, time(9, 0)),
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "product_uom_qty": 1.0,
                        "is_rental": True,
                        "price_unit": price,
                        "name": line_name,
                    },
                )
            ],
        }

    def _pitchup_cancel_order(self, order):
        if order.state == "cancel":
            return
        if order.locked:
            order.action_unlock()
        order.action_cancel()

    def _pitchup_confirm_order(self, order, booking_id):
        if order.state not in ("draft", "sent"):
            return
        try:
            with self.env.cr.savepoint():
                order.action_confirm()
        except UserError as error:
            _logger.warning(
                "Pitchup booking %s remains draft because confirmation failed: %s",
                booking_id,
                error,
            )

    def _pitchup_sync_booking(self, booking, channel):
        self.ensure_one()
        booking_id = booking.get("pretty_id") or str(booking["id"])
        order_model = self.env["sale.order"].sudo().with_company(self)
        order = order_model.search(
            [
                ("company_id", "=", self.id),
                ("client_order_ref", "=", booking_id),
                ("sale_channel_id", "=", channel.id),
            ],
            limit=1,
        )

        status = booking.get("status")
        if status == "cancelled":
            if order:
                self._pitchup_cancel_order(order)
            return "cancelled"
        if status != "confirmed":
            return "skipped"

        pitch_type_id = self._pitchup_id_from_url(booking.get("pitchtype"))
        mapping = (
            self.env["pitchup.product.mapping"]
            .sudo()
            .search(
                [
                    ("company_id", "=", self.id),
                    ("pitch_type_id", "=", pitch_type_id),
                ],
                limit=1,
            )
        )
        product = mapping.product_id
        if not product:
            raise UserError(
                _(
                    "No Odoo product mapping exists for Pitchup pitch type %(pitch_type)s.",
                    pitch_type=pitch_type_id,
                )
            )

        if not order:
            partner = self._pitchup_find_partner(booking)
            values = self._pitchup_order_values(booking, partner, channel, product)
            order = order_model.create(values)
            # Rental creation may recompute the product price; restore API truth.
            order.order_line[:1].write({"price_unit": self._pitchup_money(booking)})
            result = "created"
        else:
            result = "existing"

        self._pitchup_confirm_order(order, booking_id)
        return result

    def _sync_pitchup_orders(self):
        self.ensure_one()
        if not self.pitchup_api_key:
            raise UserError(_("Set a Pitchup API key on company %s first.", self.name))

        bookings = self._pitchup_fetch_bookings()
        channel = self._pitchup_sale_channel()
        stats = {"created": 0, "existing": 0, "cancelled": 0, "skipped": 0, "errors": 0}
        for booking in bookings:
            booking_id = booking.get("pretty_id") or booking.get("id")
            try:
                with self.env.cr.savepoint():
                    result = self._pitchup_sync_booking(booking, channel)
                stats[result] += 1
            except Exception:
                stats["errors"] += 1
                _logger.exception("Failed to sync Pitchup booking %s.", booking_id)

        _logger.info("Pitchup sync for %s completed: %s", self.display_name, stats)
        return stats

    def action_sync_pitchup_orders(self):
        totals = {"created": 0, "existing": 0, "cancelled": 0, "skipped": 0, "errors": 0}
        for company in self:
            stats = company._sync_pitchup_orders()
            for key, value in stats.items():
                totals[key] += value
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Pitchup synchronization complete"),
                "message": _(
                    "Created: %(created)s, existing: %(existing)s, "
                    "cancelled: %(cancelled)s, skipped: %(skipped)s, errors: %(errors)s",
                    **totals,
                ),
                "type": "warning" if totals["errors"] else "success",
                "sticky": bool(totals["errors"]),
            },
        }

    @api.model
    def _cron_sync_pitchup_orders(self):
        companies = self.sudo().search([("pitchup_api_key", "!=", False)])
        for company in companies:
            try:
                with self.env.cr.savepoint():
                    company._sync_pitchup_orders()
            except Exception:
                _logger.exception("Pitchup cron failed for company %s.", company.display_name)
