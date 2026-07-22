import logging
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import unquote, urlparse

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

GMAIL_ACCOUNT_PARAM = "insert_from_mail.gmail_account"
GOG_COMMAND_PARAM = "insert_from_mail.gog_command"
GOG_PASSPHRASE_PARAM = "insert_from_mail.gog_passphrase"
DEFAULT_GMAIL_ACCOUNT = "weinni2000@gmail.com"
DEFAULT_GOG_COMMAND = "/home/weinni2000/bin/gog-unlocked"
DEFAULT_WEBSITE_ID = 3


@dataclass(frozen=True)
class Booking:
    platform: str
    product_id: int
    product_name: str
    code: str
    guest_name: str
    phone: str
    email: str
    checkin: str
    checkout: str
    arrival_hour_utc: int
    nights: int
    vehicles: int | None
    adults: int | None
    message: str
    price_unit: float | None
    price_details: str


class InsertFromMail(models.Model):
    _name = "insert.from.mail"
    _description = "Insert Booking From Mail"
    _order = "create_date desc, id desc"

    name = fields.Char(default=lambda self: _("New Mail Import"), required=True)
    sender = fields.Char()
    subject = fields.Char()
    mail_url = fields.Char(string="Mail URL / Message ID")
    mail_body = fields.Text()
    platform = fields.Selection(
        [
            ("Alpacacamping", "Alpacacamping"),
            ("Roadsurfer", "Roadsurfer"),
            ("Pitchup", "Pitchup"),
        ],
        readonly=False,
    )
    booking_code = fields.Char()
    guest_name = fields.Char()
    phone = fields.Char()
    email = fields.Char()
    checkin_date = fields.Date()
    checkout_date = fields.Date()
    arrival_hour_utc = fields.Integer(default=16)
    nights = fields.Integer()
    vehicles = fields.Integer()
    adults = fields.Integer()
    message = fields.Text()
    price_unit = fields.Float()
    price_details = fields.Text()
    product_id = fields.Many2one("product.product", string="Stay Product")
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
    sale_order_id = fields.Many2one("sale.order", readonly=True, copy=False)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("extracted", "Extracted"),
            ("created", "Created"),
        ],
        default="draft",
        required=True,
        copy=False,
    )

    def action_fetch_mail_body(self):
        for import_id in self:
            import_id.mail_body = import_id._fetch_mail_body()
        return True

    def action_extract_mail(self):
        for import_id in self:
            booking = import_id._parse_booking()
            import_id._apply_booking(booking)
        return True

    def action_create_booking(self):
        for import_id in self:
            if not import_id.booking_code:
                booking = import_id._parse_booking()
                import_id._apply_booking(booking)
            import_id.sale_order_id = import_id._create_or_get_sale_order()
            import_id.state = "created"
        return True

    def action_open_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": self.sale_order_id.display_name,
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.sale_order_id.id,
        }

    def _fetch_mail_body(self):
        self.ensure_one()
        message_id = self._message_id_from_url()
        account = self.env["ir.config_parameter"].sudo().get_param(GMAIL_ACCOUNT_PARAM) or DEFAULT_GMAIL_ACCOUNT
        if not message_id and self.sender and self.subject:
            message_id = self._search_latest_message_id(account)
        if not message_id:
            raise UserError(_("Set a Gmail URL or configure sender and subject first."))
        command = [
            *self._gog_command(),
            "--account",
            account,
            "--no-input",
            "--force",
            "gmail",
            "get",
            message_id,
        ]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
                env=self._gog_env(),
            )
        except FileNotFoundError as error:
            raise UserError(
                _(
                    "Could not fetch the mail because the gog CLI is not installed "
                    "on this Odoo server. Paste the mail text into Mail Body instead."
                )
            ) from error
        except subprocess.TimeoutExpired as error:
            raise UserError(_("Fetching the mail timed out.")) from error
        if result.returncode:
            raise UserError(result.stderr.strip() or _("gog failed while fetching the mail."))
        return result.stdout

    def _search_latest_message_id(self, account):
        self.ensure_one()
        command = [
            *self._gog_command(),
            "--account",
            account,
            "--no-input",
            "--force",
            "gmail",
            "messages",
            "search",
            f'in:inbox from:"{self.sender}" subject:"{self.subject}"',
            "--max",
            "1",
            "--json",
        ]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env=self._gog_env(),
            )
        except FileNotFoundError as error:
            raise UserError(
                _(
                    "Could not search mail because the gog CLI is not installed "
                    "on this Odoo server. Paste the mail URL or body instead."
                )
            ) from error
        except subprocess.TimeoutExpired as error:
            raise UserError(_("Searching mail timed out.")) from error
        if result.returncode:
            raise UserError(result.stderr.strip() or _("gog failed while searching mail."))
        match = re.search(r'"id"\s*:\s*"([^"]+)"', result.stdout)
        return match.group(1) if match else ""

    def _gog_command(self):
        command = self.env["ir.config_parameter"].sudo().get_param(GOG_COMMAND_PARAM) or DEFAULT_GOG_COMMAND
        return shlex.split(command)

    def _gog_env(self):
        env = os.environ.copy()
        passphrase = self.env["ir.config_parameter"].sudo().get_param(GOG_PASSPHRASE_PARAM)
        if passphrase:
            env["GOGCLI_PASSPHRASE"] = passphrase
        return env

    def _message_id_from_url(self):
        self.ensure_one()
        value = (self.mail_url or "").strip()
        if not value:
            return ""
        parsed = urlparse(value)
        candidate = parsed.fragment or parsed.path or value
        candidate = unquote(candidate).rstrip("/").rsplit("/", 1)[-1]
        if "?" in candidate:
            candidate = candidate.split("?", 1)[0]
        return candidate.strip()

    def _parse_booking(self):
        self.ensure_one()
        body = self.mail_body or ""
        if not body and self.mail_url:
            body = self._fetch_mail_body()
            self.mail_body = body
        if not body:
            raise UserError(_("Set a mail URL or paste a mail body before extracting."))
        if self.platform:
            return self._parse_with_platform(body, self.platform)
        parsers = (
            self._parse_alpaka,
            self._parse_roadsurfer,
            self._parse_pitchup,
        )
        errors = []
        for parser in parsers:
            try:
                return parser(body)
            except ValueError as error:
                errors.append(str(error))
        _logger.info("Mail import parser errors: %s", errors)
        raise ValidationError(_("The mail does not match a supported booking platform."))

    def _parse_with_platform(self, body, platform):
        parsers = {
            "Alpacacamping": self._parse_alpaka,
            "Roadsurfer": self._parse_roadsurfer,
            "Pitchup": self._parse_pitchup,
        }
        return parsers[platform](body)

    def _apply_booking(self, booking):
        self.ensure_one()
        product_id = self.env["product.product"].browse(booking.product_id).exists()
        if not product_id:
            raise UserError(
                _(
                    "The parsed mail points to product ID %(product_id)s, " "but that product does not exist.",
                    product_id=booking.product_id,
                )
            )
        self.write(
            {
                "name": f"{booking.platform} {booking.code}",
                "platform": booking.platform,
                "booking_code": booking.code,
                "guest_name": booking.guest_name,
                "phone": booking.phone,
                "email": booking.email,
                "checkin_date": booking.checkin,
                "checkout_date": booking.checkout,
                "arrival_hour_utc": booking.arrival_hour_utc,
                "nights": booking.nights,
                "vehicles": booking.vehicles,
                "adults": booking.adults,
                "message": booking.message,
                "price_unit": booking.price_unit or 0.0,
                "price_details": booking.price_details,
                "product_id": product_id.id,
                "state": "extracted",
            }
        )

    def _create_or_get_sale_order(self):
        self.ensure_one()
        missing = []
        for field_name in ("platform", "booking_code", "guest_name", "product_id"):
            if not self[field_name]:
                missing.append(self._fields[field_name].string)
        if not self.checkin_date:
            missing.append(self._fields["checkin_date"].string)
        if not self.checkout_date:
            missing.append(self._fields["checkout_date"].string)
        if missing:
            raise UserError(_("Extract the mail first. Missing values: %(missing)s", missing=", ".join(missing)))
        origin = f"{self.platform} {self.booking_code}"
        order_id = (
            self.env["sale.order"]
            .sudo()
            .search(
                [
                    "|",
                    ("origin", "=", origin),
                    ("client_order_ref", "=", self.booking_code),
                ],
                limit=1,
            )
        )
        if order_id:
            self._confirm_order_if_needed(order_id)
            return order_id

        partner_id = self._find_or_create_partner()
        channel_id = self._get_sale_channel()
        line_values = {
            "product_id": self.product_id.id,
            "product_uom_qty": 1.0,
            "is_rental": True,
            "name": f"{self.product_id.display_name}\n{self.checkin_date} to {self.checkout_date}",
        }
        if self.price_unit:
            line_values["price_unit"] = self.price_unit

        values = {
            "partner_id": partner_id.id,
            "partner_invoice_id": partner_id.id,
            "partner_shipping_id": partner_id.id,
            "company_id": self.company_id.id,
            "origin": origin,
            "client_order_ref": self.booking_code,
            "note": self._booking_note(),
            "is_rental_order": True,
            "rental_start_date": self._rental_start_datetime(),
            "rental_return_date": f"{self.checkout_date} 07:00:00",
            "order_line": [(0, 0, line_values)],
        }
        if "website_id" in self.env["sale.order"]._fields and "website" in self.env.registry:
            website_id = self.env["website"].sudo().browse(DEFAULT_WEBSITE_ID).exists()
            if website_id:
                values["website_id"] = website_id.id
        if channel_id:
            values["sale_channel_id"] = channel_id.id

        order_id = self.env["sale.order"].sudo().with_company(self.company_id).create(values)
        if self.price_unit and order_id.order_line:
            order_id.order_line[:1].write({"price_unit": self.price_unit})
        self._confirm_order_if_needed(order_id)
        return order_id

    def _find_or_create_partner(self):
        self.ensure_one()
        partner_model = self.env["res.partner"].sudo()
        email = (self.email or "").strip()
        if email:
            partner_id = partner_model.search([("email", "=ilike", email)], limit=1)
            if partner_id:
                return partner_id

        phone = self.phone or ""
        digits = re.sub(r"\D", "", phone)
        if len(digits) >= 7:
            tail = digits[-9:]
            candidate_ids = partner_model.search([("phone", "like", tail)])
            partner_id = next(
                (
                    candidate_id
                    for candidate_id in candidate_ids
                    if re.sub(r"\D", "", candidate_id.phone or "").endswith(tail)
                ),
                partner_model,
            )
            if partner_id:
                return partner_id

        if self.guest_name:
            partner_id = partner_model.search([("name", "=ilike", self.guest_name)], limit=1)
            if partner_id:
                return partner_id

        return partner_model.create(
            {
                "name": self.guest_name or _("Booking guest"),
                "email": email,
                "phone": phone,
                "type": "contact",
            }
        )

    def _get_sale_channel(self):
        self.ensure_one()
        names = {
            "Roadsurfer": "Roadsurfer",
            "Pitchup": "Pitchup",
            "Alpacacamping": "Alpaca Camping",
        }
        name = names.get(self.platform)
        if not name:
            return self.env["sale.channel"]
        channel_model = self.env["sale.channel"].sudo()
        channel_id = channel_model.search(
            [
                ("name", "=ilike", name),
                ("company_id", "in", [False, self.company_id.id]),
            ],
            limit=1,
        )
        return channel_id or channel_model.create(
            {
                "name": name,
                "company_id": self.company_id.id,
            }
        )

    def _booking_note(self):
        self.ensure_one()
        details = [
            f"Imported from {self.platform} email",
            f"Booking code: {self.booking_code}",
            f"Nights: {self.nights}",
            f"Adults: {self.adults if self.adults else 'not stated'}",
            f"Vehicles: {self.vehicles if self.vehicles else 'not stated'}",
            self.price_details or "",
        ]
        if self.message:
            details.append(f"Message: {self.message}")
        if self.mail_url:
            details.append(f"Mail URL: {self.mail_url}")
        return "\n".join(details)

    def _rental_start_datetime(self):
        self.ensure_one()
        return f"{self.checkin_date} {self.arrival_hour_utc or 0:02d}:00:00"

    def _confirm_order_if_needed(self, order_id):
        self.ensure_one()
        if self.platform not in ("Roadsurfer", "Pitchup"):
            return
        if order_id.state not in ("draft", "sent"):
            return
        try:
            with self.env.cr.savepoint():
                order_id.action_confirm()
        except UserError as error:
            _logger.warning(
                "Booking %s remains draft because confirmation failed: %s",
                self.booking_code,
                error,
            )

    @staticmethod
    def _extract(body, pattern, required=True):
        match = re.search(pattern, body, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        if required:
            raise ValueError(f"Booking mail does not match expected field: {pattern}")
        return ""

    @staticmethod
    def _parse_date(value):
        months = {
            "jan": 1,
            "feb": 2,
            "mär": 3,
            "mar": 3,
            "apr": 4,
            "mai": 5,
            "may": 5,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "okt": 10,
            "oct": 10,
            "nov": 11,
            "dez": 12,
            "dec": 12,
        }
        match = re.fullmatch(
            r"(\d{1,2})\.([A-Za-zÄÖÜäöü]{3,})\.?(\d{4})",
            value.strip(),
        )
        month = match and months.get(match.group(2).lower()[:3])
        if not match or not month:
            raise ValueError(f"Unsupported booking date: {value!r}")
        return datetime(int(match.group(3)), month, int(match.group(1))).date().isoformat()

    @staticmethod
    def _parse_numeric_date(value):
        return datetime.strptime(value.strip(), "%d.%m.%Y").date().isoformat()

    @staticmethod
    def _money(value):
        if not value:
            return 0.0
        cleaned = re.sub(r"[^0-9,.-]", "", value).replace(",", ".")
        return float(cleaned)

    def _parse_alpaka(self, body):
        return Booking(
            platform="Alpacacamping",
            product_id=7699,
            product_name="Stellplatz Wohnwaagen (2P)",
            code=self._extract(body, r"^Buchungscode:\s*(\S+)"),
            guest_name=self._extract(body, r"^Name des Gastes:\s*(.+)"),
            phone=self._extract(body, r"^Telefonnr\. des Gastes:\s*(.+)", False),
            email="",
            checkin=self._parse_date(self._extract(body, r"^Checkin:\s*(.+)")),
            checkout=self._parse_date(self._extract(body, r"^Checkout:\s*(.+)")),
            arrival_hour_utc=16,
            nights=int(self._extract(body, r"^Anzahl der Nächte:\s*(\d+)")),
            vehicles=int(self._extract(body, r"^Anzahl der Fahrzeuge:\s*(\d+)")),
            adults=None,
            message=self._extract(body, r"^Nachricht deines Gastes:\s*(.+)", False),
            price_unit=None,
            price_details="Anzahl Gäste nicht angegeben; Ortstaxe prüfen",
        )

    def _parse_roadsurfer(self, body):
        period = re.search(
            r"\*\*Zeitraum:\*\*\s*(\d{2}\.\d{2}\.\d{4})\s*-\s*" r"(\d{2}\.\d{2}\.\d{4})",
            body,
            re.IGNORECASE,
        )
        if not period:
            raise ValueError("Roadsurfer Zeitraum not found")
        checkin = self._parse_numeric_date(period.group(1))
        checkout = self._parse_numeric_date(period.group(2))
        nights = (datetime.fromisoformat(checkout) - datetime.fromisoformat(checkin)).days

        guest_block = re.search(
            r"\*\*Dein Gast:\*\*\s*\\?\s*\n\s*(.+?)\s*\\?\s*\n"
            r".*?messenger.*?\n\s*([^\s]+@[^\s]+)\s*\\?\s*\n\s*(\+?\d+)",
            body,
            re.IGNORECASE | re.DOTALL,
        )
        if not guest_block:
            raise ValueError("Roadsurfer guest contact block not found")

        spot_raw = self._extract(
            body,
            r"(?s)\*\*Stellplatzgebühr gesamt:\*\*.*?<div>\s*([^<]+)",
            False,
        )
        adults_line = self._extract(
            body,
            r"(?s)\*\*Erwachsene:\*\*.*?text-right[^>]*>\s*([^<\n]+)",
            False,
        )
        service_raw = self._extract(
            body,
            r"(?s)\*\*Servicegebühr:\*\*.*?summary__total-price[^>]*>([^<]+)",
            False,
        )
        total_raw = self._extract(
            body,
            r"(?s)\*\*Gesamt \(inkl\. MwSt\.\):\*\*.*?" r"summary__total-price[^>]*>([^<]+)",
            False,
        )
        adults_match = re.search(r"\\?\*\s*(\d+)\s*\\?\*\s*\d+\s+Anzahl", adults_line)
        adults = int(adults_match.group(1)) if adults_match else None
        spot_amount = self._money(spot_raw)
        adults_amount_match = re.search(r"[€]?\s*([0-9]+[.,][0-9]{2})", adults_line)
        adults_amount = self._money(adults_amount_match.group(1)) if adults_amount_match else 0.0
        arrival = self._extract(body, r"\*\*Ankunftszeit\*\*\s*\\?\s*\n\s*(\d{1,2}):", False)
        arrival_hour_utc = max(0, int(arrival) - 2) if arrival else 16

        return Booking(
            platform="Roadsurfer",
            product_id=7699,
            product_name="Stellplatz Wohnwaagen (2P)",
            code=self._extract(body, r"\*\*Order ID:\*\*\s*\\?\s*\n\s*(\d+)"),
            guest_name=guest_block.group(1).strip(),
            email=guest_block.group(2).strip(),
            phone=guest_block.group(3).strip(),
            checkin=checkin,
            checkout=checkout,
            arrival_hour_utc=arrival_hour_utc,
            nights=nights,
            vehicles=None,
            adults=adults,
            message="",
            price_unit=spot_amount + adults_amount or None,
            price_details=(
                f"Stellplatzgebühr: {spot_raw or 'nicht gefunden'}; "
                f"Erwachsene: {adults_line or 'nicht gefunden'}; "
                f"Roadsurfer Servicegebühr: {service_raw or 'nicht gefunden'}; "
                f"Kundengesamt: {total_raw or 'nicht gefunden'}"
            ),
        )

    @staticmethod
    def _parse_pitchup_date(day, month_name, year):
        months = {
            "januar": 1,
            "februar": 2,
            "märz": 3,
            "maerz": 3,
            "april": 4,
            "mai": 5,
            "juni": 6,
            "juli": 7,
            "august": 8,
            "september": 9,
            "oktober": 10,
            "november": 11,
            "dezember": 12,
        }
        month = months.get(month_name.lower())
        if not month:
            raise ValueError(f"Unsupported Pitchup month: {month_name!r}")
        return datetime(int(year), month, int(day)).date().isoformat()

    def _parse_pitchup(self, body):
        arrival = re.search(
            r"^Ankunft:.*?(\d{1,2})\\?\.\s+([A-Za-zÄÖÜäöü]+)\s+(\d{4})",
            body,
            re.MULTILINE | re.IGNORECASE,
        )
        departure = re.search(
            r"^Abreise:.*?(\d{1,2})\\?\.\s+([A-Za-zÄÖÜäöü]+)\s+(\d{4})",
            body,
            re.MULTILINE | re.IGNORECASE,
        )
        if not arrival or not departure:
            raise ValueError("Pitchup arrival/departure not found")

        phone_raw = self._extract(body, r"^Telefon:.*?\[([^\]]+)\]", False)
        phone = re.sub(r"[^+0-9]", "", phone_raw)
        stay_raw = self._extract(body, r"^Aufenthaltskosten:.*?([0-9]+,[0-9]{2}\s*€)")
        total_raw = self._extract(body, r"^Gesamtkosten:.*?([0-9]+,[0-9]{2}\s*€)")
        commission_raw = self._extract(
            body,
            r"^Anzahlung \([^\n]+\).*?([0-9]+,[0-9]{2}\s*€)",
        )
        remainder_raw = self._extract(body, r"^Restbetrag:.*?([0-9]+,[0-9]{2}\s*€)")
        tax_raw = self._extract(
            body,
            r"^Steuer.*?Ortstaxe nicht inkludiert.*?\*\*([0-9]+,[0-9]{2}\s*€)\*\*",
            False,
        )
        adults = int(self._extract(body, r"^Teilnehmer:.*?(\d+)\s+Erwachsene"))
        checkin = self._parse_pitchup_date(*arrival.groups())
        checkout = self._parse_pitchup_date(*departure.groups())
        nights = (datetime.fromisoformat(checkout) - datetime.fromisoformat(checkin)).days

        pitch_type = self._extract(body, r"^Stellplatztyp:.*?\|\s*\|\s*(.+)$")
        pitch_type_plain = re.sub(r"[\[\]*_]", "", pitch_type)
        if "Zelt-Stellplatz" in pitch_type_plain:
            product_id, product_name = 7701, "Zeltplatz (2P)"
        elif "Wohnwagen-Stellplatz" in pitch_type_plain:
            product_id, product_name = 7699, "Stellplatz Wohnwaagen (2P)"
        elif (
            "Campervan-Stellplatz" in pitch_type_plain
            or "Power optional grass campervan campsite" in pitch_type_plain
        ):
            product_id, product_name = 7698, "Stellplatz Van (2P)"
        else:
            raise ValueError(f"Unsupported Pitchup pitch type: {pitch_type!r}")

        return Booking(
            platform="Pitchup",
            product_id=product_id,
            product_name=product_name,
            code=self._extract(body, r"Buchungs-ID:[^\n]*?([A-Z0-9]{8})"),
            guest_name=self._extract(body, r"^Name:\s*\|\s*\|\s*(.+)$"),
            phone=phone,
            email=self._extract(body, r"^E-Mail:.*?\[([^\]]+@[^\]]+)\]"),
            checkin=checkin,
            checkout=checkout,
            arrival_hour_utc=14,
            nights=nights,
            vehicles=None,
            adults=adults,
            message="",
            price_unit=self._money(total_raw),
            price_details=(
                f"Aufenthaltskosten: {stay_raw}; Gesamtkosten: {total_raw}; "
                f"Pitchup-Kommission: {commission_raw}; Restbetrag: {remainder_raw}; "
                f"Ortstaxe bei Ankunft: {tax_raw or 'nicht angegeben'}"
            ),
        )
