import base64
import io
import json
import os
import re
import shlex
import subprocess
from datetime import date, datetime, time, timedelta

import openpyxl

from odoo import Command, fields, models
from odoo.exceptions import UserError

from odoo.addons.city_tax.models._const import (
    _DESKLINE_SALUTATION_FRAU,
    _DESKLINE_SALUTATION_HERR,
)

_SHEET_ID_RE = re.compile(r"/d/([a-zA-Z0-9-_]+)")
_GID_RE = re.compile(r"[#&?]gid=(\d+)")
_CHECKIN_DATE_FORMATS = ["%m/%d/%Y", "%Y-%m-%d"]
_DOB_DATE_FORMATS = ["%m/%d/%Y", "%Y-%m-%d"]
_TINY_AWAY_CHANNEL_NAME = "Tiny Away"
_GOG_ACCOUNT_PARAM = "gog_testing.gmail_account"
_GOG_COMMAND_PARAM = "gog_testing.gog_command"
_GOG_PASSPHRASE_PARAM = "gog_testing.gog_passphrase"
_DEFAULT_GOG_ACCOUNT = "weinni2000@gmail.com"
_DEFAULT_GOG_COMMAND = "/home/weinni2000/bin/gog-unlocked"

_GENDER_TO_ANREDE = {"male": _DESKLINE_SALUTATION_HERR, "female": _DESKLINE_SALUTATION_FRAU}
_COUNTRY_ALIASES = {
    "deutschland": "Germany",
    "österreich": "Austria",
    "oesterreich": "Austria",
    "schweiz": "Switzerland",
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
_DUPLICATE_XLSX_COLUMNS = {
    "Gender": ("gender", "guest2_gender", "guest3_gender"),
    "First and Second Name": ("guest2_name", "guest3_name"),
    "Nationality": ("guest2_nationality", "guest3_nationality"),
}


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
    x_load_method = fields.Selection(
        [("gog", "Google Sheet via gog"), ("file", "Uploaded File")],
        string="Load Method",
        required=True,
        default="gog",
    )
    x_sheet_url = fields.Char(
        string="Google Sheet URL",
        help="Full Google Sheets URL. The Odoo service user's authenticated gog "
        "account must have access to the spreadsheet.",
    )
    x_file = fields.Binary(string="File", attachment=True)
    x_filename = fields.Char(string="Filename")
    x_import_warning = fields.Text(string="Import Warnings", readonly=True)
    x_month = fields.Date(
        string="Month",
        help="Any day within the target month — only the year and month are used.",
    )
    x_product_id = fields.Many2one(
        "product.product",
        string="Rental Product",
        domain="[('rent_ok', '=', True)]",
        help="Rental product added to sale orders created for this sheet.",
    )
    x_guest_tax_message_ids = fields.One2many("guest.tax.message", "x_sheet_id", string="Guest Tax Messages")

    def _get_tiny_away_sale_channel(self):
        sale_order_model = self.env["sale.order"]
        if "sale_channel_id" not in sale_order_model._fields or "sale.channel" not in self.env:
            return self.env["sale.channel"]
        return self.env["sale.channel"].search([("name", "=", _TINY_AWAY_CHANNEL_NAME)], limit=1)

    def action_load_month(self):
        self.ensure_one()
        if self.x_load_method == "file":
            return self.action_load_month_from_file()
        if not self.x_sheet_url:
            raise UserError(self.env._("Set the Google Sheet URL first."))

        sheet_id_match = _SHEET_ID_RE.search(self.x_sheet_url)
        if not sheet_id_match:
            raise UserError(self.env._("Could not find a spreadsheet ID in the URL."))
        gid_match = _GID_RE.search(self.x_sheet_url)
        gid = int(gid_match.group(1)) if gid_match else None
        rows = self._rows_with_gog(sheet_id_match.group(1), gid)
        return self._create_messages_for_month(rows)

    def action_load_month_from_file(self):
        self.ensure_one()
        if not self.x_file:
            raise UserError(self.env._("Attach a file first."))

        return self._create_messages_for_month(self._xlsx_rows(base64.b64decode(self.x_file)))

    def _run_gog_json(self, *arguments):
        parameters = self.env["ir.config_parameter"].sudo()
        account = parameters.get_param(_GOG_ACCOUNT_PARAM) or _DEFAULT_GOG_ACCOUNT
        command = parameters.get_param(_GOG_COMMAND_PARAM) or _DEFAULT_GOG_COMMAND
        gog_environment = os.environ.copy()
        passphrase = parameters.get_param(_GOG_PASSPHRASE_PARAM)
        if passphrase:
            gog_environment["GOGCLI_PASSPHRASE"] = passphrase
        try:
            result = subprocess.run(
                [
                    *shlex.split(command),
                    "--account",
                    account,
                    "--readonly",
                    "--no-input",
                    "--json",
                    *arguments,
                ],
                capture_output=True,
                check=False,
                env=gog_environment,
                text=True,
                timeout=60,
            )
        except FileNotFoundError as error:
            raise UserError(self.env._("The configured gog command was not found on this Odoo server.")) from error
        except subprocess.TimeoutExpired as error:
            raise UserError(self.env._("Reading the Google Sheet via gog timed out.")) from error
        if result.returncode:
            detail = (result.stderr or result.stdout or "Unknown gog error").strip()
            raise UserError(
                self.env._(
                    "Could not read the Google Sheet via gog: %(detail)s",
                    detail=detail,
                )
            )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise UserError(self.env._("gog returned invalid JSON.")) from exc

    def _rows_with_gog(self, spreadsheet_id, gid=None):
        metadata = self._run_gog_json("sheets", "metadata", spreadsheet_id)
        sheets = metadata.get("sheets", [])
        worksheet = next(
            (item for item in sheets if gid is None or item.get("properties", {}).get("sheetId") == gid),
            None,
        )
        if not worksheet:
            raise UserError(self.env._("Could not find the requested worksheet."))
        title = worksheet["properties"]["title"]
        escaped_title = title.replace("'", "''")
        data = self._run_gog_json("sheets", "get", spreadsheet_id, f"'{escaped_title}'")
        return self._rows_from_values(data.get("values", []))

    def _xlsx_rows(self, content):
        workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
        worksheet = workbook.worksheets[0]
        return self._rows_from_values(worksheet.iter_rows(values_only=True))

    def _rows_from_values(self, values):
        rows_iter = iter(values)
        header = [str(cell).strip() if cell else "" for cell in next(rows_iter, [])]
        occurrences = {}
        col_index = {}
        for index, column_name in enumerate(header):
            duplicate_keys = _DUPLICATE_XLSX_COLUMNS.get(column_name)
            if duplicate_keys:
                occurrence = occurrences.get(column_name, 0)
                occurrences[column_name] = occurrence + 1
                if occurrence < len(duplicate_keys):
                    col_index[duplicate_keys[occurrence]] = index
            elif column_name in _XLSX_COLUMN_MAP:
                col_index[_XLSX_COLUMN_MAP[column_name]] = index
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

        return [normalize(row) for row in rows_iter if row]

    def _create_messages_for_month(self, rows):
        self.ensure_one()
        if not self.x_month:
            raise UserError(self.env._("Select a month first."))
        target_year, target_month = self.x_month.year, self.x_month.month

        guest_tax_message = self.env["guest.tax.message"]
        created_count = 0
        skipped_count = 0
        warnings = []
        for row in rows:
            checkin = row.get("checkin")
            if not checkin or checkin.year != target_year or checkin.month != target_month:
                continue

            email = (row.get("email") or "").strip()
            import_key = f"{email}|{checkin.isoformat()}"
            existing_message = guest_tax_message.search([("x_import_key", "=", import_key)], limit=1)
            try:
                sale_order = self._find_existing_sale_order(row, existing_message)
            except UserError as error:
                warnings.append(str(error))
                continue
            if existing_message:
                self._sync_guest_data(existing_message, sale_order, row, email)
                skipped_count += 1
                continue

            guest_name = (row.get("full_name") or "Unknown").strip()
            message = guest_tax_message.create(
                {
                    "name": f"{guest_name} ({checkin.isoformat()})",
                    "x_import_key": import_key,
                    "x_sheet_id": self.id,
                    "x_sale_order_id": sale_order.id,
                    "company_id": sale_order.company_id.id,
                    "x_arrival_date": row.get("checkin"),
                    "x_departure_date": row.get("checkout"),
                }
            )
            self._sync_guest_data(message, sale_order, row, email)
            created_count += 1

        self.x_import_warning = "\n".join(warnings) or False
        message = self.env._(
            "%(created)s guest tax message(s) created, %(skipped)s already imported, " "%(warnings)s warning(s).",
            created=created_count,
            skipped=skipped_count,
            warnings=len(warnings),
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": self.env._("Sheet Loaded"), "message": message, "sticky": False},
        }

    def _find_existing_sale_order(self, row, existing_message=None):
        if existing_message and existing_message.x_sale_order_id:
            return existing_message.x_sale_order_id

        checkin = row.get("checkin")
        checkout = row.get("checkout")
        if not checkin or not checkout:
            raise UserError(self.env._("Check-in and check-out are required to find the sale order."))

        domain = [
            ("state", "!=", "cancel"),
            ("rental_start_date", ">=", datetime.combine(checkin, time.min)),
            ("rental_start_date", "<", datetime.combine(checkin + timedelta(days=1), time.min)),
            ("rental_return_date", ">=", datetime.combine(checkout, time.min)),
            ("rental_return_date", "<", datetime.combine(checkout + timedelta(days=1), time.min)),
        ]
        if self.x_product_id:
            domain.append(("order_line.product_id", "=", self.x_product_id.id))
        tiny_away_channel = self._get_tiny_away_sale_channel()
        if tiny_away_channel:
            domain.append(("sale_channel_id", "=", tiny_away_channel.id))

        candidates = self.env["sale.order"].sudo().search(domain)
        guest_name = (row.get("full_name") or "").strip().casefold()
        email = (row.get("email") or "").strip().casefold()
        matching_partner = candidates.filtered(
            lambda order: (email and (order.partner_id.email or "").strip().casefold() == email)
            or (guest_name and (order.partner_id.name or "").strip().casefold() == guest_name)
        )
        if len(matching_partner) == 1:
            return matching_partner
        if len(candidates) == 1:
            return candidates

        stay = f"{checkin.isoformat()} – {checkout.isoformat()}"
        if not candidates:
            raise UserError(
                self.env._(
                    "No existing Tiny House sale order was found for %(guest)s (%(stay)s).",
                    guest=row.get("full_name") or "Unknown guest",
                    stay=stay,
                )
            )
        raise UserError(
            self.env._(
                "Multiple Tiny House sale orders match %(guest)s (%(stay)s). Link the correct "
                "sale order manually and load again.",
                guest=row.get("full_name") or "Unknown guest",
                stay=stay,
            )
        )

    def _sync_guest_data(self, message, sale_order, row, main_email):
        message.write(
            {
                "x_sheet_id": self.id,
                "x_sale_order_id": sale_order.id,
                "company_id": sale_order.company_id.id,
                "x_arrival_date": row.get("checkin"),
                "x_departure_date": row.get("checkout"),
            }
        )
        guest_lines = self.env["x_guests_line"]
        for guest in _row_to_guests(row):
            if not guest.get("name"):
                continue
            email = main_email if guest["is_main"] else None
            preferred_partner = sale_order.partner_id if guest["is_main"] else None
            partner = self._find_or_create_partner(guest, email, preferred_partner)
            # Look up the existing guest line on the sale order itself, not just on
            # this message's own m2m link — the main guest's line is often already
            # there (auto-added by sale.order._add_partner_as_guest()) before this
            # sync ever runs, and missing that reuse used to create a duplicate.
            guest_line = sale_order.x_guest_line_ids.filtered(
                lambda line, partner=partner: line.x_guest_partner_id == partner
            )[:1]
            values = {
                "x_arrival_date_manual": message.x_arrival_date,
                "x_departure_date_manual": message.x_departure_date,
                "x_sale_order_id": sale_order.id,
                "x_guest_partner_id": partner.id,
                "x_main_guest": guest["is_main"],
                "x_save_as_contact": guest["is_main"],
            }
            if guest_line:
                guest_line.write(values)
            else:
                guest_line = guest_lines.create(values)
            if guest_line not in message.x_guest_line_ids:
                message.write({"x_guest_line_ids": [Command.link(guest_line.id)]})

        main_partner = sale_order.partner_id
        message.x_guest_line_ids.filtered(lambda line: line.x_guest_partner_id != main_partner).write(
            {"x_main_guest": False}
        )

    def _find_or_create_partner(self, guest, email, preferred_partner=None):
        partner_model = self.env["res.partner"]
        partner = preferred_partner or partner_model.browse()
        if not partner and email:
            partner = partner_model.search([("email", "=ilike", email)], limit=1)
        if not partner:
            partner = partner_model.search([("name", "=ilike", guest["name"])], limit=1)

        vals = {}
        if email:
            vals["email"] = email
        anrede = _GENDER_TO_ANREDE.get((guest.get("gender") or "").strip().lower())
        if anrede:
            vals["x_anrede"] = anrede
        if guest.get("street"):
            vals["street"] = guest["street"]
        if guest.get("city"):
            vals["city"] = guest["city"]
        if guest.get("zip"):
            vals["zip"] = str(guest["zip"])
        if guest.get("dob"):
            vals["birthdate_date"] = guest["dob"]

        country = self._find_country(guest.get("country"))
        country_vals = {"country_id": country.id, "x_nationality": country.id} if country else {}

        if partner:
            blank_vals = {key: value for key, value in vals.items() if not partner[key]}
            blank_vals.update(country_vals)
            if blank_vals:
                partner.write(blank_vals)
            return partner

        vals.update(country_vals)
        vals["name"] = guest["name"]
        return partner_model.create(vals)

    def _find_country(self, name):
        if not name:
            return None
        name = name.strip()
        if not name:
            return None
        # The sheet always gives English country names, regardless of the
        # importing user's own language — search against the English
        # translation, not whatever `res.country.name` resolves to in the
        # current context (e.g. "Czech Republic" wouldn't match under a
        # de_DE session, since that resolves to "Tschechische Republik").
        country_model = self.env["res.country"].with_context(lang="en_US")
        country = country_model.search([("name", "=ilike", name)], limit=1)
        if country:
            return country
        alias = _COUNTRY_ALIASES.get(name.lower())
        if alias:
            country = country_model.search([("name", "=ilike", alias)], limit=1)
            if country:
                return country
        # Fall back to a substring match for short/partial forms not covered by
        # the alias table (e.g. "Czech" for "Czech Republic").
        return country_model.search([("name", "ilike", name)], limit=1)

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
