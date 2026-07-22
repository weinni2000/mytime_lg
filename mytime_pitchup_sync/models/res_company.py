import base64
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

    def _pitchup_fetch_paginated(self, path, params=None):
        self.ensure_one()
        request_params = {"page_size": 100}
        request_params.update(params or {})
        data = self._pitchup_get(path, request_params)
        if isinstance(data, list):
            return data

        records = []
        while True:
            results = data.get("results")
            if results is None:
                return [data]
            records.extend(results)
            next_url = data.get("next")
            if not next_url:
                return records
            data = self._pitchup_get(next_url)

    def _pitchup_fetch_bookings(self):
        self.ensure_one()
        return self._pitchup_fetch_paginated("/booking/")

    def _pitchup_fetch_products(self):
        self.ensure_one()
        paths = ("/pitchtype/", "/pitch-type/", "/product/")
        for path in paths:
            try:
                return self._pitchup_fetch_paginated(path)
            except requests.HTTPError as error:
                if error.response is not None and error.response.status_code == 404:
                    continue
                raise
        raise UserError(
            _(
                "Could not find a Pitchup products endpoint. Tried: %(paths)s",
                paths=", ".join(paths),
            )
        )

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

    @staticmethod
    def _pitchup_product_id(product):
        if isinstance(product, dict):
            value = product.get("id") or product.get("pk") or product.get("url") or product.get("resource_uri")
            try:
                return int(value)
            except (TypeError, ValueError):
                return ResCompany._pitchup_id_from_url(value)
        return False

    @staticmethod
    def _pitchup_product_name(product):
        if not isinstance(product, dict):
            return False
        for key in ("name", "title", "display_name", "description"):
            value = product.get(key)
            if value:
                return value
        pitch_type_id = ResCompany._pitchup_product_id(product)
        return pitch_type_id and _("Pitchup pitch type %(pitch_type)s", pitch_type=pitch_type_id)

    @staticmethod
    def _pitchup_image_url_from_value(value):
        if isinstance(value, str) and value.startswith("http"):
            return value
        if isinstance(value, dict):
            for key in ("url", "image", "photo", "original", "large", "thumbnail"):
                image_url = ResCompany._pitchup_image_url_from_value(value.get(key))
                if image_url:
                    return image_url
        if isinstance(value, list):
            for item in value:
                image_url = ResCompany._pitchup_image_url_from_value(item)
                if image_url:
                    return image_url
        return False

    @staticmethod
    def _pitchup_product_detail_url(product):
        if not isinstance(product, dict):
            return False
        for key in ("url", "resource_uri", "self"):
            value = product.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value
        return False

    @staticmethod
    def _pitchup_product_image_url(product):
        if not isinstance(product, dict):
            return False
        for key in (
            "image",
            "images",
            "photo",
            "photos",
            "picture",
            "pictures",
            "media",
            "gallery",
        ):
            image_url = ResCompany._pitchup_image_url_from_value(product.get(key))
            if image_url:
                return image_url
        return False

    def _pitchup_product_with_image_data(self, product):
        self.ensure_one()
        if self._pitchup_product_image_url(product):
            return product

        detail_url = self._pitchup_product_detail_url(product)
        if not detail_url:
            return product
        try:
            detail = self._pitchup_get(detail_url)
        except requests.RequestException:
            _logger.exception("Could not fetch Pitchup product detail from %s.", detail_url)
            return product
        if isinstance(detail, dict):
            combined = dict(product)
            combined.update(detail)
            return combined
        return product

    def _pitchup_download_image(self, image_url):
        self.ensure_one()
        response = requests.get(
            image_url,
            headers={
                "Authorization": f"Token {self.pitchup_api_key}",
                "User-Agent": "mytime_pitchup_sync/19.0",
            },
            timeout=PITCHUP_TIMEOUT,
        )
        response.raise_for_status()
        content_type = response.headers.get("Content-Type") or ""
        if content_type and not content_type.startswith("image/"):
            raise UserError(
                _(
                    "Pitchup image URL returned %(content_type)s instead of an image: %(url)s",
                    content_type=content_type,
                    url=image_url,
                )
            )
        return base64.b64encode(response.content)

    def _pitchup_update_product_image(self, product_template_id, product_data):
        self.ensure_one()
        image_url = self._pitchup_product_image_url(product_data)
        if not image_url:
            return False

        try:
            product_template_id.write({"image_1920": self._pitchup_download_image(image_url)})
        except requests.RequestException:
            _logger.exception(
                "Could not download Pitchup image %s for product %s.",
                image_url,
                product_template_id.display_name,
            )
            return False
        return True

    def _pitchup_find_or_create_product_template(self, pitch_type_id, name):
        self.ensure_one()
        product_template_model = self.env["product.template"].sudo().with_company(self)
        default_code = f"PITCHUP-{pitch_type_id}"
        product_template_id = product_template_model.search(
            [
                ("default_code", "=", default_code),
                ("company_id", "in", [False, self.id]),
            ],
            limit=1,
        )
        if product_template_id:
            product_template_id.write(
                {
                    "name": name,
                    "purchase_ok": False,
                    "rent_ok": True,
                    "sale_ok": True,
                    "type": "service",
                    "planning_enabled": True,
                    "x_is_a_room_offer": True,
                }
            )
            return product_template_id
        return product_template_model.create(
            {
                "name": name,
                "default_code": default_code,
                "purchase_ok": False,
                "rent_ok": True,
                "sale_ok": True,
                "type": "service",
                "planning_enabled": True,
                "x_is_a_room_offer": True,
                "company_id": self.id,
            }
        )

    def _download_pitchup_products(self):
        self.ensure_one()
        if not self.pitchup_api_key:
            raise UserError(_("Set a Pitchup API key on company %(company)s first.", company=self.name))

        product_values = self._pitchup_fetch_products()
        mapping_model = self.env["pitchup.product.mapping"].sudo()
        stats = {"created": 0, "updated": 0, "images": 0, "skipped": 0}
        for product_data in product_values:
            product_data = self._pitchup_product_with_image_data(product_data)
            pitch_type_id = self._pitchup_product_id(product_data)
            name = self._pitchup_product_name(product_data)
            if not pitch_type_id or not name:
                stats["skipped"] += 1
                _logger.warning("Skipped Pitchup product with incomplete data: %s", product_data)
                continue

            product_template_id = self._pitchup_find_or_create_product_template(pitch_type_id, name)
            if self._pitchup_update_product_image(product_template_id, product_data):
                stats["images"] += 1
            mapping_id = mapping_model.search(
                [
                    ("company_id", "=", self.id),
                    ("pitch_type_id", "=", pitch_type_id),
                ],
                limit=1,
            )
            values = {
                "pitch_type_id": pitch_type_id,
                "pitch_type_name": name,
                "product_template_id": product_template_id.id,
                "company_id": self.id,
            }
            if mapping_id:
                mapping_id.write(values)
                stats["updated"] += 1
            else:
                mapping_model.create(values)
                stats["created"] += 1

        _logger.info("Pitchup product download for %s completed: %s", self.display_name, stats)
        return stats

    def _pitchup_prepare_unmapped_wizard_action(self, line_values):
        self.ensure_one()
        wizard_id = self.env["pitchup.sync.wizard"].create(
            {
                "company_id": self.id,
                "sync_unmapped_only": True,
                "line_ids": [(0, 0, values) for values in line_values],
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Map Pitchup Products"),
            "res_model": "pitchup.sync.wizard",
            "view_mode": "form",
            "res_id": wizard_id.id,
            "target": "new",
        }

    def _sync_pitchup_product_mappings(self):
        self.ensure_one()
        if not self.pitchup_api_key:
            raise UserError(_("Set a Pitchup API key on company %(company)s first.", company=self.name))

        product_values = self._pitchup_fetch_products()
        mapping_model = self.env["pitchup.product.mapping"].sudo()
        existing_mapping_ids = mapping_model.search([("company_id", "=", self.id)])
        existing_by_pitch_type = {mapping_id.pitch_type_id: mapping_id for mapping_id in existing_mapping_ids}
        line_values = []
        stats = {"updated": 0, "images": 0, "unmapped": 0, "skipped": 0}
        for product_data in product_values:
            product_data = self._pitchup_product_with_image_data(product_data)
            pitch_type_id = self._pitchup_product_id(product_data)
            name = self._pitchup_product_name(product_data)
            if not pitch_type_id or not name:
                stats["skipped"] += 1
                _logger.warning("Skipped Pitchup product with incomplete data: %s", product_data)
                continue

            mapping_id = existing_by_pitch_type.get(pitch_type_id)
            if mapping_id:
                mapping_id.write({"pitch_type_name": name})
                if self._pitchup_update_product_image(mapping_id.product_template_id, product_data):
                    stats["images"] += 1
                stats["updated"] += 1
                continue

            line_values.append(
                {
                    "pitch_type_id": pitch_type_id,
                    "pitch_type_name": name,
                }
            )
            stats["unmapped"] += 1

        _logger.info("Pitchup mapping sync for %s completed: %s", self.display_name, stats)
        return stats, line_values

    def _pitchup_order_values(self, booking, partner, channel, product_template_id):
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
        product_id = product_template_id.product_variant_id
        line_name = f"{product_template_id.display_name}\n{arrive} 18:00 to {depart} 09:00"
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
                        "product_id": product_id.id,
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
        product_template_id = mapping.product_template_id
        if not product_template_id:
            raise UserError(
                _(
                    "No Odoo product mapping exists for Pitchup pitch type %(pitch_type)s.",
                    pitch_type=pitch_type_id,
                )
            )

        if not order:
            partner = self._pitchup_find_partner(booking)
            values = self._pitchup_order_values(booking, partner, channel, product_template_id)
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
            raise UserError(_("Set a Pitchup API key on company %(company)s first.", company=self.name))

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

    def action_download_pitchup_products(self):
        totals = {"created": 0, "updated": 0, "images": 0, "skipped": 0}
        for company in self:
            stats = company._download_pitchup_products()
            for key, value in stats.items():
                totals[key] += value
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Pitchup products downloaded"),
                "message": _(
                    "Created: %(created)s, updated: %(updated)s, " "images: %(images)s, skipped: %(skipped)s",
                    **totals,
                ),
                "type": "warning" if totals["skipped"] else "success",
                "sticky": bool(totals["skipped"]),
            },
        }

    def action_sync_pitchup_product_mappings(self):
        self.ensure_one()
        stats, line_values = self._sync_pitchup_product_mappings()
        if line_values:
            return self._pitchup_prepare_unmapped_wizard_action(line_values)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Pitchup product mappings synchronized"),
                "message": _(
                    "Updated: %(updated)s, images: %(images)s, skipped: %(skipped)s",
                    **stats,
                ),
                "type": "warning" if stats["skipped"] else "success",
                "sticky": bool(stats["skipped"]),
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
