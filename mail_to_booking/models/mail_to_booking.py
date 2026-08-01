import json
import logging
import re
from io import BytesIO

import requests
from pdfminer.high_level import extract_text as extract_pdf_text

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import email_split, html2plaintext, plaintext2html

from ._const import (
    DEEPSEEK_API_URL,
    DEEPSEEK_MODEL,
    DEEPSEEK_PRODUCT_MATCH_PROMPT,
    DEEPSEEK_SYSTEM_PROMPT,
    DEEPSEEK_TIMEOUT,
)

_logger = logging.getLogger(__name__)

_STYLE_SCRIPT_RE = re.compile(r"<(style|script)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)


class MailToBooking(models.Model):
    _name = "mail.to.booking"
    _description = "Mail to Booking Import"
    _inherit = ["mail.thread"]
    _order = "create_date desc, id desc"

    name = fields.Char(default=lambda self: _("New Booking Mail"), required=True)
    fetchmail_server_id = fields.Many2one("fetchmail.server", readonly=True, ondelete="cascade")
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
    sender = fields.Char(readonly=True)
    subject = fields.Char(readonly=True)
    mail_body = fields.Text(readonly=True)
    is_booking = fields.Boolean(readonly=True)
    sale_channel_id = fields.Many2one("sale.channel")
    booking_code = fields.Char(readonly=True)
    guest_name = fields.Char(readonly=True)
    phone = fields.Char(readonly=True)
    email = fields.Char(readonly=True)
    checkin_date = fields.Date(readonly=True)
    checkout_date = fields.Date(readonly=True)
    nights = fields.Integer(readonly=True)
    adults = fields.Integer(readonly=True)
    vehicles = fields.Integer(readonly=True)
    price_unit = fields.Float(readonly=True)
    product_hint = fields.Char(readonly=True)
    product_id = fields.Many2one("product.product", readonly=True)
    message = fields.Text(readonly=True)
    sale_order_id = fields.Many2one("sale.order", readonly=True, copy=False)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("skipped", "Not a Booking"),
            ("no_product", "Product Missing"),
            ("created", "Booking Created"),
            ("error", "Error"),
        ],
        default="draft",
        required=True,
        copy=False,
    )
    error_message = fields.Text(readonly=True)
    confirm_warning = fields.Text(readonly=True)

    def action_view_sale_order(self):
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

    def action_retry(self):
        for record in self:
            record._run_extraction(record.mail_body)
        return True

    def action_reprocess(self):
        for record in self:
            if record.sale_order_id:
                record.sale_order_id.unlink()
            record.write(
                {
                    "sale_order_id": False,
                    "product_id": False,
                    "mail_body": record._rebuild_mail_body_from_source(),
                }
            )
            record._run_extraction(record.mail_body)
        return True

    def action_process(self):
        for record in self:
            record._create_booking()
        return True

    def action_remove_booking(self):
        for record in self:
            record._remove_sale_order()
            record.write({"state": "draft", "confirm_warning": False})
        return True

    def action_open_product_mapping_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Choose Product"),
            "res_model": "mail.to.booking.product.mapping.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_id": self.id},
        }

    def action_open_not_a_booking_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Not a Booking"),
            "res_model": "mail.to.booking.not.booking.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_id": self.id},
        }

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        server_id = self.env["fetchmail.server"].browse(self.env.context.get("default_fetchmail_server_id"))
        mail_body = self._build_mail_body(msg_dict.get("body") or "", msg_dict.get("attachments") or [])
        values = {
            "name": msg_dict.get("subject") or _("New Booking Mail"),
            "fetchmail_server_id": server_id.id,
            "sender": msg_dict.get("email_from") or "",
            "subject": msg_dict.get("subject") or "",
            "mail_body": mail_body,
        }
        if server_id:
            values["company_id"] = server_id.company_id.id
        if isinstance(custom_values, dict):
            values.update(custom_values)
        record = self.create(values)
        record._run_extraction(record.mail_body)
        return record

    @staticmethod
    def _build_mail_body(body_html, attachments):
        mail_body = MailToBooking._clean_html_body(body_html)
        pdf_text = MailToBooking._extract_pdf_attachments_text(attachments)
        if pdf_text:
            mail_body = f"{mail_body}\n\n--- PDF attachment ---\n{pdf_text}"
        return mail_body

    def _rebuild_mail_body_from_source(self):
        # mail_body is a derived, one-shot snapshot taken by message_new. Once
        # any bug in that derivation is fixed, already-imported records still
        # carry the old, broken snapshot forever unless it's regenerated from
        # the original incoming email, which mail.thread keeps in the chatter.
        self.ensure_one()
        email_message = (
            self.message_ids.sudo().filtered(lambda message: message.message_type == "email").sorted("id")
        )
        if not email_message:
            return self.mail_body
        email_message = email_message[0]
        attachments = [(attachment.name, attachment.raw) for attachment in email_message.attachment_ids]
        return self._build_mail_body(email_message.body or "", attachments)

    @staticmethod
    def _clean_html_body(body_html):
        # html2plaintext strips tags but not the CSS/JS text inside <style>/
        # <script> blocks, which some marketing-template emails (e.g. VanSite)
        # pack with several KB of inline CSS. Left in, that noise pushes the
        # actual booking details past the DeepSeek truncation cutoff.
        body_html = _STYLE_SCRIPT_RE.sub("", body_html)
        text = html2plaintext(body_html)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    @staticmethod
    def _extract_pdf_attachments_text(attachments):
        # Entries are (filename, content) or (filename, content, info) depending
        # on how they were parsed; index instead of unpacking to accept both.
        texts = []
        for attachment in attachments:
            filename, content = attachment[0], attachment[1]
            if not filename.lower().endswith(".pdf"):
                continue
            try:
                texts.append(extract_pdf_text(BytesIO(content)))
            except Exception:  # noqa: BLE001
                _logger.exception("Mail to Booking could not read PDF attachment %s.", filename)
        return "\n\n".join(text for text in texts if text)

    def _run_extraction(self, body_text):
        self.ensure_one()
        blocklist_channel_id = self._guess_sale_channel_from_sender()
        if blocklist_channel_id and self._is_subject_blocklisted(blocklist_channel_id):
            self.write(
                {
                    "sale_channel_id": blocklist_channel_id.id,
                    "is_booking": False,
                    "state": "skipped",
                    "error_message": False,
                }
            )
            return
        try:
            extraction = self._call_deepseek(body_text or "")
        except (UserError, requests.RequestException, ValueError, KeyError, IndexError) as error:
            self.write({"state": "error", "error_message": str(error)})
            _logger.warning("Mail to Booking extraction failed for %s: %s", self.display_name, error)
            self._notify_warning(_("DeepSeek extraction failed: %(error)s", error=str(error)))
            return
        self._apply_extraction(extraction)
        if not self.is_booking:
            self.state = "skipped"
            return
        self._create_booking()

    def _notify_warning(self, body):
        self.ensure_one()
        user_id = self.fetchmail_server_id.notify_user_id
        if not user_id:
            return
        self.message_notify(
            partner_ids=user_id.partner_id.ids,
            subject=_("Mail to Booking warning: %(name)s", name=self.display_name),
            body=body,
        )

    def _call_deepseek(self, body_text):
        return self._call_deepseek_chat(DEEPSEEK_SYSTEM_PROMPT, body_text[:12000])

    def _call_deepseek_chat(self, system_prompt, user_content):
        self.ensure_one()
        api_key = self.company_id.sudo().deepseek_api_key
        if not api_key:
            raise UserError(
                _(
                    "Set a DeepSeek API key on company %(company)s first.",
                    company=self.company_id.name,
                )
            )
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        response = requests.post(
            DEEPSEEK_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=DEEPSEEK_TIMEOUT,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)

    def _apply_extraction(self, extraction):
        self.ensure_one()
        is_booking = bool(extraction.get("is_booking"))
        values = {
            "is_booking": is_booking,
            "booking_code": extraction.get("code") or "",
            "guest_name": extraction.get("guest_name") or "",
            "phone": extraction.get("phone") or "",
            "email": extraction.get("email") or "",
            "checkin_date": extraction.get("checkin_date") or False,
            "checkout_date": extraction.get("checkout_date") or False,
            "nights": extraction.get("nights") or 0,
            "adults": extraction.get("adults") or 0,
            "vehicles": extraction.get("vehicles") or 0,
            "price_unit": extraction.get("price_unit") or 0.0,
            "product_hint": extraction.get("product_hint") or "",
            "message": extraction.get("message") or "",
            "state": "draft",
            "error_message": False,
        }
        if is_booking:
            values["sale_channel_id"] = self._find_or_create_sale_channel(extraction.get("platform")).id
        self.write(values)

    def _create_booking(self):
        self.ensure_one()
        product_id = self._find_product()
        if not product_id:
            self.write(
                {
                    "sale_order_id": False,
                    "product_id": False,
                    "state": "no_product",
                    "confirm_warning": False,
                }
            )
            self._notify_warning(
                _(
                    'No product could be matched for hint "%(hint)s".',
                    hint=self.product_hint,
                )
            )
            return self.env["sale.order"]

        partner_id = self._find_or_create_partner()
        is_rental = bool(self.checkin_date and self.checkout_date)
        order_values = {
            "partner_id": partner_id.id,
            "partner_invoice_id": partner_id.id,
            "partner_shipping_id": partner_id.id,
            "company_id": self.company_id.id,
            "sale_channel_id": self.sale_channel_id.id,
            "origin": f"Mail to Booking ({self.sale_channel_id.name or 'unknown platform'})",
            "client_order_ref": self.booking_code,
            "note": self._booking_note(),
        }
        if is_rental:
            order_values.update(
                {
                    "is_rental_order": True,
                    "rental_start_date": f"{self.checkin_date} 14:00:00",
                    "rental_return_date": f"{self.checkout_date} 10:00:00",
                }
            )
        line_values = {
            "product_id": product_id.id,
            "product_uom_qty": 1.0,
            "is_rental": is_rental,
            "name": product_id.display_name,
        }
        if self.price_unit:
            line_values["price_unit"] = self.price_unit
        order_values["order_line"] = [(0, 0, line_values)]

        order_id = self.env["sale.order"].sudo().with_company(self.company_id).create(order_values)
        order_id.message_post(
            body=self._mail_chatter_body(),
            subject=self.subject or _("Imported booking mail"),
        )
        confirm_warning = self._confirm_sale_order(order_id)
        self.write(
            {
                "sale_order_id": order_id.id,
                "product_id": product_id.id,
                "state": "created",
                "confirm_warning": confirm_warning,
            }
        )
        if confirm_warning:
            self._notify_warning(
                _(
                    "Booking %(order)s was created but could not be confirmed: %(error)s",
                    order=order_id.display_name,
                    error=confirm_warning,
                )
            )
        return order_id

    def _confirm_sale_order(self, order_id):
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                order_id.action_confirm()
        except UserError as error:
            _logger.warning(
                "Mail to Booking could not confirm sale order %s: %s",
                order_id.display_name,
                error,
            )
            return str(error)
        return False

    def _guess_sale_channel_from_sender(self):
        # Best-effort channel resolution from the sender address, used for the
        # subject-blocklist check: the real channel is normally only known
        # after DeepSeek extraction has run.
        self.ensure_one()
        sender_emails = email_split(self.sender or "")
        if not sender_emails:
            return self.env["sale.channel"]
        return (
            self.env["sale.channel"]
            .sudo()
            .search(
                [
                    ("email", "=ilike", sender_emails[0]),
                    ("company_id", "in", [False, self.company_id.id]),
                ],
                limit=1,
            )
        )

    def _is_subject_blocklisted(self, sale_channel_id):
        self.ensure_one()
        subject = (self.subject or "").lower()
        if not subject:
            return False
        blocklist_ids = (
            self.env["mail.to.booking.subject.blocklist"]
            .sudo()
            .search([("sale_channel_id", "=", sale_channel_id.id)])
        )
        return any(entry.subject_keyword and entry.subject_keyword.lower() in subject for entry in blocklist_ids)

    def _remove_sale_order(self):
        self.ensure_one()
        order_id = self.sale_order_id
        if not order_id:
            return
        try:
            with self.env.cr.savepoint():
                if order_id.state not in ("draft", "sent", "cancel"):
                    order_id.action_cancel()
                order_id.unlink()
        except UserError as error:
            _logger.warning(
                "Mail to Booking could not delete sale order %s, cancelling instead: %s",
                order_id.display_name,
                error,
            )
            order_id.action_cancel()
        self.write({"sale_order_id": False, "product_id": False})

    def _find_or_create_sale_channel(self, name):
        self.ensure_one()
        name = name or _("Direct")
        channel_model = self.env["sale.channel"].sudo()
        channel_id = channel_model.search(
            [
                ("name", "=ilike", name),
                ("company_id", "in", [False, self.company_id.id]),
            ],
            limit=1,
        )
        if channel_id:
            return channel_id
        sender_emails = email_split(self.sender or "")
        return channel_model.create(
            {
                "name": name,
                "company_id": self.company_id.id,
                "email": sender_emails[0] if sender_emails else False,
            }
        )

    def _find_product(self):
        self.ensure_one()
        if self.sale_channel_id.force_single_product and self.sale_channel_id.default_product_id:
            return self.sale_channel_id.default_product_id
        if not self.product_hint:
            return self.env["product.product"]

        mapping_model = self.env["mail.to.booking.product.mapping"].sudo()
        mapping_id = mapping_model.search(
            [
                ("sale_channel_id", "=", self.sale_channel_id.id),
                ("product_hint", "=ilike", self.product_hint),
            ],
            limit=1,
        )
        if mapping_id:
            return mapping_id.product_id

        allowed_product_ids = self.fetchmail_server_id.allowed_product_ids
        if allowed_product_ids:
            product_id = self._match_allowed_product(allowed_product_ids)
            if product_id:
                self._create_product_mapping(product_id)
            return product_id

        candidate_ids = (
            self.env["product.product"]
            .sudo()
            .search(
                [
                    ("name", "ilike", self.product_hint),
                    ("company_id", "in", [False, self.company_id.id]),
                    "|",
                    ("rent_ok", "=", True),
                    ("sale_ok", "=", True),
                ]
            )
        )
        if len(candidate_ids) != 1:
            return self.env["product.product"]

        product_id = candidate_ids[0]
        self._create_product_mapping(product_id)
        return product_id

    def _match_allowed_product(self, allowed_product_ids):
        self.ensure_one()
        candidates = "\n".join(
            f"{index}. {product_id.display_name}" for index, product_id in enumerate(allowed_product_ids, start=1)
        )
        user_content = f"Description: {self.product_hint}\n\nCandidates:\n{candidates}"
        try:
            result = self._call_deepseek_chat(DEEPSEEK_PRODUCT_MATCH_PROMPT, user_content)
            match_index = result.get("match_index")
        except (UserError, requests.RequestException, ValueError, KeyError, IndexError) as error:
            _logger.warning("Mail to Booking product match failed for %s: %s", self.display_name, error)
            return self.env["product.product"]
        if not isinstance(match_index, int) or not (1 <= match_index <= len(allowed_product_ids)):
            return self.env["product.product"]
        return allowed_product_ids[match_index - 1]

    def _create_product_mapping(self, product_id):
        self.ensure_one()
        self.env["mail.to.booking.product.mapping"].sudo().create(
            {
                "sale_channel_id": self.sale_channel_id.id,
                "product_hint": self.product_hint,
                "product_id": product_id.id,
                "company_id": self.company_id.id,
            }
        )

    def _is_email_excluded(self, email):
        # A shared/forwarding mailbox (e.g. buchungen@weingartmair.eu) can be
        # the "email" DeepSeek extracts for many different guests. Matching a
        # res.partner on that address would silently reassign the booking to
        # whichever guest happened to be created first (e.g. a "Gina
        # Andersen" booking landing on an existing "August Schlag" partner),
        # so such addresses must never drive a reverse partner lookup - only
        # the guest_name found in the message may.
        self.ensure_one()
        return bool(
            self.env["mail.to.booking.excluded.email"]
            .sudo()
            .search_count(
                [
                    ("email", "=ilike", email),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
        )

    def _find_or_create_partner(self):
        self.ensure_one()
        partner_model = self.env["res.partner"].sudo()
        email = (self.email or "").strip()
        if email and not self._is_email_excluded(email):
            partner_id = partner_model.search([("email", "=ilike", email)], limit=1)
            if partner_id:
                return partner_id

        digits = re.sub(r"\D", "", self.phone or "")
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
                "phone": self.phone or "",
                "type": "contact",
            }
        )

    def _booking_note(self):
        self.ensure_one()
        details = [
            _(
                "Imported from %(platform)s email",
                platform=self.sale_channel_id.name or _("an unknown platform"),
            ),
            _("Booking code: %(code)s", code=self.booking_code or _("not stated")),
            _("Nights: %(nights)s", nights=self.nights or _("not stated")),
            _("Adults: %(adults)s", adults=self.adults or _("not stated")),
            _("Vehicles: %(vehicles)s", vehicles=self.vehicles or _("not stated")),
        ]
        if self.message:
            details.append(_("Message: %(message)s", message=self.message))
        return "\n".join(details)

    def _mail_chatter_body(self):
        self.ensure_one()
        lines = [
            f"From: {self.sender or ''}",
            f"Subject: {self.subject or ''}",
            "",
            self.mail_body or "",
        ]
        return plaintext2html("\n".join(lines))
