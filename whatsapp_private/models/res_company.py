import base64
import json
import logging
import subprocess
import sys
from pathlib import Path

from odoo import _, fields, models, tools
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    whatsapp_private_qr_code = fields.Binary(
        string="WhatsApp QR Code",
        compute="_compute_whatsapp_private_state",
        attachment=False,
    )
    whatsapp_private_status = fields.Char(
        string="Connection Status",
        compute="_compute_whatsapp_private_state",
    )
    whatsapp_private_status_detail = fields.Text(
        string="Status Detail",
        compute="_compute_whatsapp_private_state",
    )

    def _whatsapp_private_directory(self):
        self.ensure_one()
        data_dir = Path(tools.config.get("data_dir") or "/var/lib/odoo")
        return data_dir / "whatsapp_private" / f"company_{self.id}"

    def _whatsapp_private_worker(self):
        return Path(__file__).resolve().parents[1] / "misc" / "whatsapp_worker.py"

    def _read_whatsapp_private_state(self):
        self.ensure_one()
        directory = self._whatsapp_private_directory()
        state_path = directory / "state.json"
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"status": "not_linked", "detail": _("Not linked")}

    def _compute_whatsapp_private_state(self):
        labels = {
            "not_linked": _("Not linked"),
            "starting": _("Starting"),
            "waiting_for_qr": _("Waiting for QR scan"),
            "connected": _("Connected"),
            "sending": _("Sending"),
            "sent": _("Message sent"),
            "error": _("Error"),
            "timeout": _("QR login timed out"),
        }
        for company in self:
            state = company._read_whatsapp_private_state()
            status = state.get("status", "not_linked")
            company.whatsapp_private_status = labels.get(status, status)
            company.whatsapp_private_status_detail = state.get("detail")
            try:
                qr_data = (company._whatsapp_private_directory() / "qr.png").read_bytes()
            except OSError:
                qr_data = b""
            company.whatsapp_private_qr_code = base64.b64encode(qr_data) if qr_data else False

    def action_whatsapp_private_connect(self):
        self.ensure_one()
        if not self.id:
            raise UserError(_("Save the company before linking WhatsApp."))
        directory = self._whatsapp_private_directory()
        directory.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            str(self._whatsapp_private_worker()),
            "link",
            "--directory",
            str(directory),
            "--timeout",
            "300",
        ]
        log_file = (directory / "worker.log").open("ab")
        try:
            subprocess.Popen(  # pylint: disable=consider-using-with
                command,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        except OSError as exc:
            raise UserError(_("Could not start the WhatsApp linking process: %s", exc)) from exc
        finally:
            log_file.close()
        return self.action_whatsapp_private_refresh()

    def action_whatsapp_private_refresh(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "res.company",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_whatsapp_private_open_send_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Send WhatsApp Message"),
            "res_model": "whatsapp.send.message.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_company_id": self.id},
        }

    def _send_private_whatsapp_message(self, phone, message):
        self.ensure_one()
        directory = self._whatsapp_private_directory()
        directory.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            str(self._whatsapp_private_worker()),
            "send",
            "--directory",
            str(directory),
            "--phone",
            phone,
            "--message",
            message,
            "--timeout",
            "90",
        ]
        _logger.info(
            "Sending private WhatsApp message to %s for company %s (%s).",
            phone,
            self.id,
            self.name,
        )
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=105,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            _logger.exception("Private WhatsApp send subprocess could not be completed for %s.", phone)
            raise UserError(_("WhatsApp sender could not be completed: %s", exc)) from exc
        if result.returncode:
            _logger.warning(
                "Private WhatsApp send to %s failed (exit code %s): %s",
                phone,
                result.returncode,
                result.stderr.strip() or result.stdout.strip(),
            )
            raise UserError(
                result.stderr.strip() or result.stdout.strip() or _("The WhatsApp message could not be sent.")
            )
        _logger.info("Private WhatsApp send to %s completed.\n%s", phone, result.stdout.strip())
        return True
