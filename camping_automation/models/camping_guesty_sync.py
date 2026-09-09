import json
import logging
import re
from datetime import datetime

import requests

from odoo import models

_logger = logging.getLogger(__name__)

GUESTY_REPORT_API = "https://app.guesty.com/report/api/v2"
GUESTY_VIEW_ID = "65ae70023122d700522b5985"
GUESTY_TOKEN_PARAM = "camping_automation.guesty_token"

ODOO_COMPANY_ID = 12

# Maps a Guesty listingId to the Odoo records needed to book it.
# Only the Tiny House listing (the one behind GUESTY_VIEW_ID) is configured.
LISTING_CONFIG = {
    "64c9abb9122f53003f923323": {
        "product_id": 7706,  # product.product "Tiny House"
        "product_name": "Tiny House",
        "resource_id": 2607,  # resource.resource "Tiny House" (the only unit)
        "role_id": 12,  # planning.role "Tiny House Prod" (resource 2607 + product 3140, sync_shift_rental=True)
        "sale_channel_id": 1,  # sale.channel "Tiny Away"
    },
}


class CampingGuestySync(models.Model):
    _name = "camping.guesty.sync"
    _description = "Import Guesty reservations as Odoo rental bookings"

    def _cron_import_guesty_reservations(self):
        """Entry point called by the scheduled action (twice a day)."""
        self._import_reservations()

    def _guesty_get(self, token, path, params=None):
        response = requests.get(
            f"{GUESTY_REPORT_API}{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _fetch_reservations(self, token):
        view = self._guesty_get(token, f"/views/{GUESTY_VIEW_ID}")
        params = {
            "fields": view["fields"],
            "limit": 100,
            "skip": 0,
            "sort": view.get("sort", "checkIn"),
            "timezone": "Europe/Vienna",
            "filters": json.dumps(view["filters"]),
            "requestFromDashboard": "true",
            "reservationsListAdapter": "true",
            "includeLocalTimes": "true",
        }
        data = self._guesty_get(token, "/reservations", params)
        return view, data.get("results", [])

    @staticmethod
    def _phone_digits(phone):
        return re.sub(r"\D", "", phone or "")

    def _find_partner_by_phone(self, phone):
        digits = self._phone_digits(phone)
        if len(digits) < 7:
            return self.env["res.partner"]
        # Compare on the last 9 digits so +43/0043/0 prefixes all match.
        tail = digits[-9:]
        candidates = self.env["res.partner"].sudo().search([("phone", "like", tail)])
        return next(
            (c for c in candidates if self._phone_digits(c.phone).endswith(tail)),
            self.env["res.partner"],
        )

    @staticmethod
    def _parse_guesty_dt(iso_utc):
        return datetime.strptime(iso_utc, "%Y-%m-%dT%H:%M:%S.%fZ")

    @staticmethod
    def _fmt_dmy_hm(dt):
        return dt.strftime("%d/%m/%Y %H:%M")

    def _import_reservations(self):
        token = self.env["ir.config_parameter"].sudo().get_param(GUESTY_TOKEN_PARAM)
        if not token:
            _logger.warning(
                "Camping Automation: %s system parameter is not set, skipping Guesty import.",
                GUESTY_TOKEN_PARAM,
            )
            return

        try:
            view, reservations = self._fetch_reservations(token)
        except Exception:
            _logger.exception("Camping Automation: failed to fetch reservations from Guesty.")
            return

        _logger.info(
            "Camping Automation: Guesty view %r returned %d reservation(s).",
            view.get("title"),
            len(reservations),
        )

        for reservation in reservations:
            try:
                with self.env.cr.savepoint():
                    self._import_one_reservation(reservation)
            except Exception:
                _logger.exception(
                    "Camping Automation: failed to import Guesty reservation %s.",
                    reservation.get("_id"),
                )

    def _import_one_reservation(self, reservation):
        guesty_id = reservation["_id"]
        listing_id = reservation["listingId"]
        config = LISTING_CONFIG.get(listing_id)
        if not config:
            _logger.warning(
                "Camping Automation: no LISTING_CONFIG mapping for listingId=%s, skipping reservation %s.",
                listing_id,
                guesty_id,
            )
            return

        sale_order_model = self.env["sale.order"].sudo()
        if sale_order_model.search([("client_order_ref", "=", guesty_id)], limit=1):
            return  # already imported by a previous run

        guest = reservation.get("guest") or {}
        guest_name = guest.get("fullName") or "Guesty guest"
        guest_phone = guest.get("phone")
        check_in = self._parse_guesty_dt(reservation["checkIn"])
        check_out = self._parse_guesty_dt(reservation["checkOut"])

        partner = self._find_partner_by_phone(guest_phone)
        if not partner:
            partner = (
                self.env["res.partner"]
                .sudo()
                .create(
                    {
                        "name": guest_name,
                        "phone": guest_phone,
                    }
                )
            )

        order_line_name = (
            f"{config['product_name']}\n"
            f"{self._fmt_dmy_hm(check_in)} to {self._fmt_dmy_hm(check_out)}"
            f" ({guest_name})"
        )

        order = sale_order_model.create(
            {
                "partner_id": partner.id,
                "company_id": ODOO_COMPANY_ID,
                "sale_channel_id": config["sale_channel_id"],
                "client_order_ref": guesty_id,
                "x_order_involves_room": True,
                "is_rental_order": True,
                "rental_start_date": check_in,
                "rental_return_date": check_out,
                "pitch_resource_ids": [(6, 0, [config["resource_id"]])],
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": config["product_id"],
                            "is_rental": True,
                            "product_uom_qty": 1.0,
                            "price_unit": 0.0,
                            "name": order_line_name,
                        },
                    )
                ],
            }
        )

        # Odoo may snap the requested times to the property's actual
        # check-in/out rules, so use the order's own dates (post-compute)
        # rather than the raw Guesty times for the planning slot.
        self.env["planning.slot"].sudo().create(
            {
                "resource_id": config["resource_id"],
                "role_id": config["role_id"],
                "company_id": ODOO_COMPANY_ID,
                "sale_line_id": order.order_line[0].id,
                "sale_order_id": order.id,
                "start_datetime": order.rental_start_date,
                "end_datetime": order.rental_return_date,
                "x_guests": reservation.get("guestsCount") or 0,
            }
        )

        order.action_confirm()
        _logger.info(
            "Camping Automation: imported Guesty reservation %s as %s (partner %s).",
            guesty_id,
            order.name,
            partner.name,
        )
