import json
import logging
import os
import resource
import secrets
import signal
import socket
import subprocess
import sys
import time

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools import config

_logger = logging.getLogger(__name__)
_LOGIN_URL = "https://admin.booking.com/"
_WORKER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "misc",
    "external",
    "booking_playwright_worker.py",
)


def _reset_child_limits():
    for sig in (signal.SIGCHLD, signal.SIGPIPE, signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, signal.SIG_DFL)
        except (ValueError, OSError) as exc:
            _logger.debug("Could not reset signal %s in Booking worker: %s", sig, exc)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
    except (ValueError, OSError) as exc:
        _logger.debug("Could not remove the Booking worker memory limit: %s", exc)


class BookingAccount(models.Model):
    _name = "booking.account"
    _description = "Booking Account"

    temp_booking_key = fields.Char()
    username = fields.Char(string="Booking.com Username")
    password = fields.Char(string="Booking.com Password", groups="base.group_system")
    login_url = fields.Char(default=_LOGIN_URL)
    session_cookies = fields.Text(groups="base.group_system", readonly=True)
    login_state = fields.Selection(
        [
            ("not_connected", "Not connected"),
            ("logging_in", "Logging in"),
            ("waiting_human", "Waiting for human verification"),
            ("waiting_sms", "Waiting for SMS"),
            ("connected", "Connected"),
            ("error", "Error"),
        ],
        default="not_connected",
        readonly=True,
    )
    login_error = fields.Text(readonly=True)
    last_login = fields.Datetime(readonly=True)
    vnc_password = fields.Char(string="Challenge Session Password", groups="base.group_system", readonly=True)
    worker_pid = fields.Integer(string="Browser Worker PID", groups="base.group_system", readonly=True)

    def _stop_existing_worker(self):
        self.ensure_one()
        pid = self.worker_pid
        if not pid:
            return
        command_path = f"/proc/{pid}/cmdline"
        try:
            with open(command_path, "rb") as command_file:
                command = command_file.read().decode(errors="replace")
            if "booking_playwright_worker.py" not in command:
                _logger.warning("Refusing to stop PID %s because it is not a Booking worker.", pid)
                self.worker_pid = False
                return
            os.killpg(pid, signal.SIGTERM)
            for _attempt in range(30):
                if not os.path.exists(command_path):
                    break
                time.sleep(0.1)
            # The worker and its display helpers share this process group. If
            # anything ignored SIGTERM, do not leave fixed VNC ports occupied.
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError as exc:
                _logger.debug("Booking worker process group %s already stopped: %s", pid, exc)
        except ProcessLookupError as exc:
            _logger.debug("Booking worker PID %s already stopped: %s", pid, exc)
        except OSError as exc:
            _logger.warning("Could not stop previous Booking worker PID %s: %s", pid, exc)
        self.worker_pid = False

    def _challenge_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": (
                "/booking-novnc/vnc.html?autoconnect=1&resize=scale"
                "&path=booking-novnc/websockify"
                f"&password={self.vnc_password}"
            ),
            "target": "new",
        }

    @staticmethod
    def _is_booking_display_command(command):
        return any(
            marker in command
            for marker in (
                "booking_playwright_worker.py",
                "Xvfb\0:90\0",
                "x11vnc\0-display\0:90\0-rfbport\05901\0",
                "websockify\0--web\0/usr/share/novnc\0127.0.0.1:6080\0",
            )
        )

    def action_close_booking_processes(self):
        """Stop the active worker and verified orphaned Booking display helpers."""
        self.ensure_one()
        self._stop_existing_worker()
        process_ids = []
        own_uid = os.getuid()
        for entry in os.listdir("/proc"):
            if not entry.isdigit() or int(entry) == os.getpid():
                continue
            process_path = os.path.join("/proc", entry)
            try:
                if os.stat(process_path).st_uid != own_uid:
                    continue
                with open(os.path.join(process_path, "cmdline"), "rb") as command_file:
                    command = command_file.read().decode(errors="replace")
                if self._is_booking_display_command(command):
                    process_ids.append(int(entry))
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                continue

        for pid in process_ids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError as exc:
                _logger.debug("Booking helper PID %s already stopped: %s", pid, exc)
        time.sleep(0.5)
        for pid in process_ids:
            if os.path.exists(f"/proc/{pid}"):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError as exc:
                    _logger.debug("Booking helper PID %s already stopped: %s", pid, exc)

        self.write(
            {
                "worker_pid": False,
                "vnc_password": False,
                "login_state": "not_connected",
                "login_error": False,
            }
        )
        _logger.info(
            "Closed %s orphaned Booking browser helper process(es) for account %s.",
            len(process_ids),
            self.id,
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Booking.com browser closed"),
                "message": self.env._("Closed %s hanging process(es).", len(process_ids)),
                "type": "success",
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_booking_login(self):
        self.ensure_one()
        if not self.username or not self.password:
            raise UserError(self.env._("Set the Booking.com username and password first."))
        if not os.path.exists(_WORKER_PATH):
            raise UserError(self.env._("Booking.com Playwright worker was not found."))

        self._stop_existing_worker()

        baseline_id = self.search([], order="id desc", limit=1).id
        profile_dir = os.path.join(
            config.get("data_dir"),
            "booking_manual",
            f"account_{self.id}",
        )
        login_url = self.login_url or _LOGIN_URL
        if "op_token=" in login_url:
            _logger.info("Ignoring expired one-time Booking op_token URL for account %s.", self.id)
            login_url = _LOGIN_URL
        worker_request = {
            "account_id": self.id,
            "baseline_id": baseline_id,
            "username": self.username,
            "password": self.password,
            "login_url": login_url,
            "database": self.env.cr.dbname,
            "db_host": config.get("db_host"),
            "db_port": config.get("db_port"),
            "db_user": config.get("db_user"),
            "db_password": config.get("db_password"),
            "vnc_password": secrets.token_urlsafe(6)[:8],
            "profile_dir": profile_dir,
            "session_cookies": self.session_cookies,
        }
        self.write(
            {
                "login_state": "logging_in",
                "login_error": False,
                "vnc_password": worker_request["vnc_password"],
            }
        )

        try:
            process = subprocess.Popen(
                [sys.executable, _WORKER_PATH],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                preexec_fn=_reset_child_limits,
                start_new_session=True,
            )
            process.stdin.write(json.dumps(worker_request))
            process.stdin.close()
            self.worker_pid = process.pid
        except OSError as exc:
            self.login_state = "error"
            self.login_error = str(exc)
            raise UserError(self.env._("Could not start the Booking.com login worker.")) from exc

        _logger.info("Started Booking.com login worker PID %s for account %s.", process.pid, self.id)
        for _attempt in range(50):
            try:
                with socket.create_connection(("127.0.0.1", 6080), timeout=0.1):
                    return self._challenge_action()
            except OSError:
                time.sleep(0.1)
        raise UserError(self.env._("The interactive Booking.com browser did not become ready."))

    def action_open_booking_challenge(self):
        self.ensure_one()
        if not self.vnc_password or self.login_state not in ("logging_in", "waiting_human"):
            raise UserError(self.env._("No interactive Booking.com browser session is active."))
        return self._challenge_action()
