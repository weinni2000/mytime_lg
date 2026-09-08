import base64
import json
import logging
import os
import re
import shlex
import subprocess
import tempfile
from datetime import timedelta

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GMAIL_ACCOUNT_PARAM = "invoice_from_mail.gmail_account"
GOG_COMMAND_PARAM = "invoice_from_mail.gog_command"
GOG_PASSPHRASE_PARAM = "invoice_from_mail.gog_passphrase"
DEFAULT_GMAIL_ACCOUNT = "weinni2000@gmail.com"
DEFAULT_GOG_COMMAND = "/home/weinni2000/bin/gog-unlocked"
SEARCH_WINDOW_DAYS = 30
SEARCH_MAX_MESSAGES = 5

# Matches document/invoice numbers such as "RE2026/0208" or "AR5035/2026" that
# vendors embed in the payment reference: a short letter prefix directly
# followed by a run of digits, a separator, and more digits. Deliberately
# narrower than "any digit run" so it does not also pick up IBANs or internal
# reference codes (e.g. "FE/000003579") that never appear as plain text in
# the invoice email itself.
DOCUMENT_NUMBER_PATTERN = re.compile(r"[A-Za-z]{1,6}\d{2,6}[-/]\d{1,10}")


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    def action_search_invoice_in_mail(self):
        self.ensure_one()
        match = self._find_invoice_mail()
        if not match:
            raise UserError(_("No matching email with a PDF attachment was found for this transaction."))
        attachment_info, pdf_content = self._download_invoice_attachment(match["message_id"], match["attachment"])
        attachment = self.env["ir.attachment"].create(
            {
                "name": attachment_info["filename"],
                "mimetype": attachment_info.get("mimeType") or "application/pdf",
                "datas": base64.b64encode(pdf_content),
            }
        )
        return self.with_context(statement_line_id=self.id).create_document_from_attachment(attachment.ids)

    def _find_invoice_mail(self):
        self.ensure_one()
        for query in self._build_mail_search_queries():
            messages = self._gog_search_messages(query, SEARCH_MAX_MESSAGES)
            for message_summary in messages:
                message = self._gog_get_message(message_summary["id"])
                pdf_attachment = next(
                    (
                        attachment
                        for attachment in message.get("attachments", [])
                        if attachment.get("mimeType") == "application/pdf"
                    ),
                    None,
                )
                if pdf_attachment:
                    return {"message_id": message_summary["id"], "attachment": pdf_attachment}
        return None

    def _build_mail_search_queries(self):
        """Build candidate Gmail queries, most specific first.

        The invoiced amount often only appears inside the PDF attachment, not
        in the surrounding email text, so an amount-only query can miss the
        right mail. Vendors' bank payment references almost always embed the
        document number instead (e.g. "RE2026/0208"), which usually *does*
        appear verbatim in the invoice mail's subject or body, so it is tried
        first.
        """
        self.ensure_one()
        base_parts = ["has:attachment", "filename:pdf"]
        if self.partner_id.email:
            base_parts.append(f"from:{self.partner_id.email}")
        elif self.partner_name:
            base_parts.append(f'"{self.partner_name}"')
        date_parts = []
        if self.date:
            after = (self.date - timedelta(days=SEARCH_WINDOW_DAYS)).strftime("%Y/%m/%d")
            before = (self.date + timedelta(days=SEARCH_WINDOW_DAYS)).strftime("%Y/%m/%d")
            date_parts = [f"after:{after}", f"before:{before}"]

        amount_dot = f"{abs(self.amount):.2f}"
        amount_comma = amount_dot.replace(".", ",")

        queries = [
            " ".join([*base_parts, f'"{document_number}"', *date_parts])
            for document_number in self._extract_document_numbers()
        ]
        queries.append(" ".join([*base_parts, f'("{amount_dot}" OR "{amount_comma}")', *date_parts]))
        return queries

    def _extract_document_numbers(self):
        self.ensure_one()
        text = self.payment_ref or ""
        document_numbers = []
        for document_number in DOCUMENT_NUMBER_PATTERN.findall(text):
            if document_number not in document_numbers:
                document_numbers.append(document_number)
        return document_numbers

    def _download_invoice_attachment(self, message_id, attachment_info):
        self.ensure_one()
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = os.path.join(tmp_dir, attachment_info["filename"])
            self._gog_run(
                [
                    "gmail",
                    "attachment",
                    message_id,
                    attachment_info["attachmentId"],
                    "--out",
                    out_path,
                ],
                timeout=60,
            )
            with open(out_path, "rb") as pdf_file:
                pdf_content = pdf_file.read()
        return attachment_info, pdf_content

    def _gog_search_messages(self, query, limit):
        result = self._gog_run(["gmail", "messages", "search", query, "--max", str(limit)])
        return result.get("messages", [])

    def _gog_get_message(self, message_id):
        return self._gog_run(["gmail", "get", message_id, "--format", "full"], timeout=60)

    def _gog_run(self, args, timeout=30):
        self.ensure_one()
        account = self.env["ir.config_parameter"].sudo().get_param(GMAIL_ACCOUNT_PARAM) or DEFAULT_GMAIL_ACCOUNT
        command = [
            *self._gog_command(),
            "--account",
            account,
            "--no-input",
            "--force",
            "--json",
            *args,
        ]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._gog_env(),
            )
        except FileNotFoundError as error:
            raise UserError(
                _("Could not search mail because the gog CLI is not installed " "on this Odoo server.")
            ) from error
        except subprocess.TimeoutExpired as error:
            raise UserError(_("Searching mail timed out.")) from error
        if result.returncode:
            raise UserError(result.stderr.strip() or _("gog failed while searching mail."))
        return json.loads(result.stdout or "{}")

    def _gog_command(self):
        command = self.env["ir.config_parameter"].sudo().get_param(GOG_COMMAND_PARAM) or DEFAULT_GOG_COMMAND
        return shlex.split(command)

    def _gog_env(self):
        env = os.environ.copy()
        passphrase = self.env["ir.config_parameter"].sudo().get_param(GOG_PASSPHRASE_PARAM)
        if passphrase:
            env["GOGCLI_PASSPHRASE"] = passphrase
        return env
