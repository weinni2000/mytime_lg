import base64
import csv
import io
import re
from datetime import date, datetime

import openpyxl
import requests

from odoo import fields, models
from odoo.exceptions import UserError

from odoo.addons.city_tax.models._const import (
    _DESKLINE_SALUTATION_FRAU,
    _DESKLINE_SALUTATION_HERR,
)

_SHEET_ID_RE = re.compile(r"/d/([a-zA-Z0-9-_]+)")
_GID_RE = re.compile(r"[#&?]gid=(\d+)")
_CHECKIN_DATE_FORMATS = ["%m/%d/%Y", "%Y-%m-%d"]
_DOB_DATE_FORMATS = ["%m/%d/%Y", "%Y-%m-%d"]

_GENDER_TO_ANREDE = {"male": _DESKLINE_SALUTATION_HERR, "female": _DESKLINE_SALUTATION_FRAU}
_COUNTRY_ALIASES = {
    "deutschland": "Germany",
    "österreich": "Austria",
    "oesterreich": "Austria",
    "schweiz": "Switzerland",
}

# csv (guest_registration_sheet.csv, as used by submit_service_summary.py) header -> normalized key
_CSV_COLUMN_MAP = {
    "email": "email",
    "checkin": "checkin",
    "checkout": "checkout",
    "full_name": "full_name",
    "gender": "gender",
    "country": "country",
    "street": "street",
    "dob": "dob",
    "city": "city",
    "zip": "zip",
    "guest2_name": "guest2_name",
    "guest2_gender": "guest2_gender",
    "guest2_nationality": "guest2_nationality",
}

# xlsx (Google Forms "Responses" export) header -> normalized row key
_XLSX_COLUMN_MAP = {
    "Email Address": "email",
    "Check In Date": "checkin",
    "Check Out Date": "checkout",
    "Full Name": "full_name",
    "Gender": "gender",
    "Country": "country",
    "Street": "street",
    "Date of Birth": "dob",
    "City": "city",
    "Zip Code": "zip",
    "First and Second Name": "guest2_name",
    "Gender 2": "guest2_gender",
    "Nationality": "guest2_nationality",
    "First and Second Name 2": "guest3_name",
    "Gender 3": "guest3_gender",
    "Nationality 2": "guest3_nationality",
}
_XLSX_REQUIRED_COLUMNS = {"email", "checkin", "full_name"}


def _clean(value):
    return value.strip() if isinstance(value, str) else value


def _clean_zip(value):
    """openpyxl reads numeric-looking xlsx cells (e.g. zip codes) as floats,
    so a zip of 18000 comes back as 18000.0 — strip that artifact."""
    value = _clean(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip() if value else value


def _row_to_guests(row):
    """Build the [main_guest, *additional_guests] list from a normalized row dict."""
    guests = [
        {
            "name": _clean(row.get("full_name")),
            "gender": _clean(row.get("gender")),
            "country": _clean(row.get("country")),
            "street": _clean(row.get("street")),
            "dob": row.get("dob"),
            "city": _clean(row.get("city")),
            "zip": _clean_zip(row.get("zip")),
            "is_main": True,
        }
    ]
    for prefix in ("guest2", "guest3"):
        name = _clean(row.get(f"{prefix}_name"))
        if not name:
            continue
        guests.append(
            {
                "name": name,
                "gender": _clean(row.get(f"{prefix}_gender")),
                "country": _clean(row.get(f"{prefix}_nationality")),
                # Additional guests have no address of their own in the sheet —
                # they're staying at the same place as the main guest.
                "street": guests[0]["street"],
                "city": guests[0]["city"],
                "zip": guests[0]["zip"],
                "is_main": False,
            }
        )
    return guests


class GuestTaxSheet(models.Model):
    _name = "guest.tax.sheet"
    _description = "Guest Tax Google Sheet"

    name = fields.Char(required=True)
    x_sheet_url = fields.Char(
        string="Google Sheet URL",
        help="Full Google Sheets URL, e.g. .../spreadsheets/d/<id>/edit#gid=<gid>. "
        "The sheet must be shared as 'Anyone with the link can view'.",
    )
    x_file = fields.Binary(string="File", attachment=True)
    x_filename = fields.Char(string="Filename")
    x_month = fields.Date(
        string="Month",
        help="Any day within the target month — only the year and month are used.",
    )
    x_guest_tax_message_ids = fields.One2many("guest.tax.message", "x_sheet_id", string="Guest Tax Messages")

    def action_load_month(self):
        self.ensure_one()
        if not self.x_sheet_url:
            raise UserError(self.env._("Set the Google Sheet URL first."))

        sheet_id_match = _SHEET_ID_RE.search(self.x_sheet_url)
        if not sheet_id_match:
            raise UserError(self.env._("Could not find a spreadsheet ID in the URL."))
        gid_match = _GID_RE.search(self.x_sheet_url)

        export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id_match.group(1)}/export?format=csv"
        if gid_match:
            export_url += f"&gid={gid_match.group(1)}"

        response = requests.get(export_url, timeout=30)
        if not response.ok or "<!DOCTYPE html" in response.text[:200]:
            raise UserError(
                self.env._(
                    "Could not download the sheet as CSV (HTTP %(status)s). Make sure it is "
                    "shared as 'Anyone with the link can view'.",
                    status=response.status_code,
                )
            )

        def normalize(row):
            data = {key: row.get(column) for column, key in _CSV_COLUMN_MAP.items()}
            data["checkin"] = self._parse_date(data["checkin"], _CHECKIN_DATE_FORMATS)
            data["checkout"] = self._parse_date(data.get("checkout"), _CHECKIN_DATE_FORMATS)
            data["dob"] = self._parse_date(data.get("dob"), _DOB_DATE_FORMATS)
            return data

        rows = (normalize(row) for row in csv.DictReader(io.StringIO(response.text)))
        return self._create_messages_for_month(rows)

    def action_load_month_from_file(self):
        self.ensure_one()
        if not self.x_file:
            raise UserError(self.env._("Attach a file first."))

        workbook = openpyxl.load_workbook(
            io.BytesIO(base64.b64decode(self.x_file)), data_only=True, read_only=True
        )
        worksheet = workbook.worksheets[0]
        rows_iter = worksheet.iter_rows(values_only=True)
        header = [str(cell).strip() if cell else "" for cell in next(rows_iter)]
        col_index = {
            key: header.index(column_name)
            for column_name, key in _XLSX_COLUMN_MAP.items()
            if column_name in header
        }
        missing = _XLSX_REQUIRED_COLUMNS - set(col_index)
        if missing:
            raise UserError(
                self.env._(
                    "The file is missing expected column(s): %(columns)s",
                    columns=", ".join(sorted(missing)),
                )
            )

        def cell(row, key):
            index = col_index.get(key)
            return row[index] if index is not None and index < len(row) else None

        def normalize(row):
            checkin_value = cell(row, "checkin")
            checkout_value = cell(row, "checkout")
            dob_value = cell(row, "dob")
            return {
                "email": cell(row, "email"),
                "checkin": self._to_date(checkin_value, _CHECKIN_DATE_FORMATS),
                "checkout": self._to_date(checkout_value, _CHECKIN_DATE_FORMATS),
                "full_name": cell(row, "full_name"),
                "gender": cell(row, "gender"),
                "country": cell(row, "country"),
                "street": cell(row, "street"),
                "dob": self._to_date(dob_value, _DOB_DATE_FORMATS),
                "city": cell(row, "city"),
                "zip": cell(row, "zip"),
                "guest2_name": cell(row, "guest2_name"),
                "guest2_gender": cell(row, "guest2_gender"),
                "guest2_nationality": cell(row, "guest2_nationality"),
                "guest3_name": cell(row, "guest3_name"),
                "guest3_gender": cell(row, "guest3_gender"),
                "guest3_nationality": cell(row, "guest3_nationality"),
            }

        rows = (normalize(row) for row in rows_iter if row)
        return self._create_messages_for_month(rows)

    def _create_messages_for_month(self, rows):
        self.ensure_one()
        if not self.x_month:
            raise UserError(self.env._("Select a month first."))
        target_year, target_month = self.x_month.year, self.x_month.month

        guest_tax_message = self.env["guest.tax.message"]
        created_count = 0
        skipped_count = 0
        for row in rows:
            checkin = row.get("checkin")
            if not checkin or checkin.year != target_year or checkin.month != target_month:
                continue

            email = (row.get("email") or "").strip()
            import_key = f"{email}|{checkin.isoformat()}"
            if guest_tax_message.search_count([("x_import_key", "=", import_key)]):
                skipped_count += 1
                continue

            guest_name = (row.get("full_name") or "Unknown").strip()
            message = guest_tax_message.create(
                {
                    "name": f"{guest_name} ({checkin.isoformat()})",
                    "x_import_key": import_key,
                    "x_sheet_id": self.id,
                    "x_arrival_date": row.get("checkin"),
                    "x_departure_date": row.get("checkout"),
                }
            )
            self._create_guest_lines(message, row, email)
            created_count += 1

        message = self.env._(
            "%(created)s guest tax message(s) created, %(skipped)s already imported.",
            created=created_count,
            skipped=skipped_count,
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": self.env._("Sheet Loaded"), "message": message, "sticky": False},
        }

    def _create_guest_lines(self, message, row, main_email):
        y_guests_line = self.env["y_guests_line"]
        for guest in _row_to_guests(row):
            if not guest.get("name"):
                continue
            partner = self._find_or_create_partner(guest, main_email if guest["is_main"] else None)
            y_guests_line.create(
                {
                    "x_group_id": message.id,
                    "x_guest_partner_id": partner.id,
                    "x_main_guest": guest["is_main"],
                    "x_save_as_contact": guest["is_main"],
                }
            )

    def _find_or_create_partner(self, guest, email):
        partner_model = self.env["res.partner"]
        partner = partner_model.browse()
        if email:
            partner = partner_model.search([("email", "=ilike", email)], limit=1)
        if not partner:
            partner = partner_model.search([("name", "=ilike", guest["name"])], limit=1)

        vals = {}
        anrede = _GENDER_TO_ANREDE.get((guest.get("gender") or "").strip().lower())
        if anrede:
            vals["x_anrede"] = anrede
        country = self._find_country(guest.get("country"))
        if country:
            vals["country_id"] = country.id
            vals["x_nationality"] = country.id
        if guest.get("street"):
            vals["street"] = guest["street"]
        if guest.get("city"):
            vals["city"] = guest["city"]
        if guest.get("zip"):
            vals["zip"] = str(guest["zip"])
        if guest.get("dob"):
            vals["x_birthdate"] = guest["dob"]

        if partner:
            # Enrich only fields the existing partner doesn't already have —
            # never overwrite data that's already there.
            blank_vals = {key: value for key, value in vals.items() if not partner[key]}
            if blank_vals:
                partner.write(blank_vals)
            return partner

        vals["name"] = guest["name"]
        if email:
            vals["email"] = email
        return partner_model.create(vals)

    def _find_country(self, name):
        if not name:
            return None
        name = name.strip()
        if not name:
            return None
        country = self.env["res.country"].search([("name", "=ilike", name)], limit=1)
        if country:
            return country
        alias = _COUNTRY_ALIASES.get(name.lower())
        if alias:
            country = self.env["res.country"].search([("name", "=ilike", alias)], limit=1)
            if country:
                return country
        # Fall back to a substring match for short/partial forms not covered by
        # the alias table (e.g. "Czech" for "Czech Republic").
        return self.env["res.country"].search([("name", "ilike", name)], limit=1)

    @classmethod
    def _to_date(cls, value, formats):
        """Normalize a CSV string, an xlsx datetime/date cell, or None into a date."""
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return cls._parse_date(str(value) if value else None, formats)

    @staticmethod
    def _parse_date(value, formats):
        if not value:
            return None
        value = value.strip()
        for date_format in formats:
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue
        return None
