import base64
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from odoo import _, fields, models, tools
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    whatsapp_private_qr_code = fields.Binary(
        string="WhatsApp QR Code",
        compute="_compute_whatsapp_private_state",
        inverse="_inverse_whatsapp_private_qr_code",
        attachment=False,
        help=(
            "The QR image displayed on the company form. Replacing this image does not "
            "replace the linked-device session; use Recreate QR Code for a fresh session."
        ),
    )
    whatsapp_private_qr_live = fields.Binary(
        string="Live WhatsApp QR Code",
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
            "resetting": _("Resetting connection"),
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
            encoded_qr = base64.b64encode(qr_data) if qr_data else False
            company.whatsapp_private_qr_code = encoded_qr
            company.whatsapp_private_qr_live = encoded_qr

    def get_whatsapp_private_live_qr(self):
        self.ensure_one()
        self.check_access("read")
        directory = self._whatsapp_private_directory()
        qr_path = directory / "qr.png"
        try:
            qr_data = qr_path.read_bytes()
            updated_at = time.strftime("%H:%M:%S UTC", time.gmtime(qr_path.stat().st_mtime))
        except OSError:
            qr_data = b""
            updated_at = ""
        state = self._read_whatsapp_private_state()
        return {
            "qr": base64.b64encode(qr_data).decode() if qr_data else False,
            "status": state.get("status", "not_linked"),
            "detail": state.get("detail", ""),
            "updatedAt": updated_at,
        }

    def _inverse_whatsapp_private_qr_code(self):
        for company in self:
            directory = company._whatsapp_private_directory()
            directory.mkdir(parents=True, exist_ok=True)
            qr_path = directory / "qr.png"
            if not company.whatsapp_private_qr_code:
                qr_path.unlink(missing_ok=True)
                continue
            try:
                qr_data = base64.b64decode(company.whatsapp_private_qr_code, validate=True)
            except (ValueError, TypeError) as exc:
                raise UserError(_("The uploaded QR code is not valid image data.")) from exc
            temporary = directory / "qr.png.upload"
            temporary.write_bytes(qr_data)
            os.replace(temporary, qr_path)

    def action_whatsapp_private_delete_qr(self):
        self.ensure_one()
        (self._whatsapp_private_directory() / "qr.png").unlink(missing_ok=True)
        return self.action_whatsapp_private_refresh()

    def _whatsapp_private_worker_pids(self, operations=("link", "listen")):
        """Return exact worker PIDs for this company and the requested operations."""
        self.ensure_one()
        worker = str(self._whatsapp_private_worker().resolve())
        directory = str(self._whatsapp_private_directory().resolve())
        operations = set(operations)
        pids = []
        for process_dir in Path("/proc").iterdir():
            if not process_dir.name.isdigit():
                continue
            try:
                arguments = (process_dir / "cmdline").read_bytes().decode().split("\0")
                worker_index = arguments.index(worker)
                operation = arguments[worker_index + 1]
                directory_index = arguments.index("--directory")
            except (OSError, UnicodeDecodeError, ValueError, IndexError):
                continue
            if (
                operation in operations
                and directory_index + 1 < len(arguments)
                and str(Path(arguments[directory_index + 1]).resolve()) == directory
            ):
                pids.append(int(process_dir.name))
        return pids

    @staticmethod
    def _whatsapp_private_process_running(pid):
        try:
            state = (Path("/proc") / str(pid) / "stat").read_text().split()[2]
        except (OSError, IndexError):
            return False
        return state != "Z"

    def _stop_whatsapp_private_workers(self):
        self.ensure_one()
        pids = self._whatsapp_private_worker_pids()
        for pid in pids:
            try:
                os.kill(pid, 15)
            except ProcessLookupError:
                continue
        deadline = time.monotonic() + 10
        while any(self._whatsapp_private_process_running(pid) for pid in pids):
            if time.monotonic() >= deadline:
                raise UserError(_("Could not stop the existing private WhatsApp worker. Try again shortly."))
            time.sleep(0.1)

    def action_whatsapp_private_recreate_qr(self):
        """Discard this company session and start a completely fresh QR link."""
        self.ensure_one()
        directory = self._whatsapp_private_directory()
        directory.mkdir(parents=True, exist_ok=True)
        self._stop_whatsapp_private_workers()
        for filename in (
            "session.db",
            "session.db-shm",
            "session.db-wal",
            "qr.png",
            "heartbeat",
            "state.json",
            "listener.pid",
            "link.pid",
        ):
            (directory / filename).unlink(missing_ok=True)
        for queue_path in (directory / "outbox").glob("*"):
            if queue_path.is_file():
                queue_path.unlink(missing_ok=True)
        (directory / "state.json").write_text(
            json.dumps(
                {
                    "status": "resetting",
                    "detail": "Creating a new WhatsApp QR code.",
                    "updated_at": time.time(),
                }
            ),
            encoding="utf-8",
        )
        _logger.warning("Private WhatsApp session reset for company %s (%s).", self.id, self.name)
        return self.action_whatsapp_private_connect()

    def action_whatsapp_private_connect(self):
        self.ensure_one()
        if not self.id:
            raise UserError(_("Save the company before linking WhatsApp."))
        directory = self._whatsapp_private_directory()
        directory.mkdir(parents=True, exist_ok=True)
        if self._whatsapp_private_worker_pids():
            return self.action_whatsapp_private_refresh()
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
