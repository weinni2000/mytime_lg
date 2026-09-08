import json
import logging
import os
import shlex
import subprocess

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GMAIL_ACCOUNT_PARAM = "gog_testing.gmail_account"
GOG_COMMAND_PARAM = "gog_testing.gog_command"
GOG_PASSPHRASE_PARAM = "gog_testing.gog_passphrase"
DEFAULT_GMAIL_ACCOUNT = "weinni2000@gmail.com"
DEFAULT_GOG_COMMAND = "/home/weinni2000/bin/gog-unlocked"
SEARCH_MAX_MESSAGES = 10


class ResCompany(models.Model):
    _inherit = "res.company"

    search_term = fields.Char()
    gog_test_mail_ids = fields.Many2many("gog.test.mail", string="GOG Test Mails")

    def action_search_gmail(self):
        self.ensure_one()
        if not self.search_term:
            raise UserError(_("Enter a search term first."))
        result = self._gog_run(
            ["gmail", "messages", "search", self.search_term, "--max", str(SEARCH_MAX_MESSAGES)]
        )
        mail_model = self.env["gog.test.mail"]
        records = mail_model
        for message in result.get("messages", []):
            record = mail_model.search([("message_id", "=", message["id"])], limit=1)
            vals = {
                "message_id": message["id"],
                "subject": message.get("subject"),
                "sender": message.get("from"),
                "mail_date": message.get("date"),
            }
            if record:
                record.write(vals)
            else:
                record = mail_model.create(vals)
            records |= record
        self.gog_test_mail_ids = [(6, 0, records.ids)]

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
