import json
import logging
import os
import resource
import signal
import subprocess
import sys

import requests

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_DESKLINE_BASE_URL = "https://webclient4.deskline.net"
_DESKLINE_REGION = "AT2"
_PLAYWRIGHT_WORKER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "misc",
    "external",
    "deskline_playwright_worker.py",
)


def _reset_child_limits():
    # Odoo's worker/arbiter process installs custom SIGCHLD (and other) signal
    # handling to manage its own child processes, and (from limit_memory_soft in
    # the config) an RLIMIT_AS virtual-address-space cap to protect itself from
    # runaway requests. Both are inherited straight through subprocess.run()
    # unless reset here. The RLIMIT_AS cap is the actual cause of Chromium dying
    # with SIGTRAP on launch: its sandboxed multi-process architecture reserves
    # far more virtual address space at startup than Odoo's soft memory limit
    # allows, even though its real (RSS) memory usage is much lower.
    for sig in (signal.SIGCHLD, signal.SIGPIPE, signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, signal.SIG_DFL)
        except (ValueError, OSError) as exc:
            _logger.debug("Could not reset signal %s: %s", sig, exc)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
    except (ValueError, OSError) as exc:
        _logger.debug("Could not reset RLIMIT_AS: %s", exc)


class ResCompany(models.Model):
    _inherit = "res.company"

    x_deskline_username = fields.Char(string="Deskline Username")
    x_deskline_password = fields.Char(string="Deskline Password")
    x_deskline_property_id = fields.Char(
        string="Deskline Property ID",
        help="GUID after /visitorregistrationforms/savevtsheet/ in the Deskline submission URL. "
        "Auto-filled by 'Log in to Deskline' when discoverable, but can be corrected manually.",
    )
    x_deskline_db_ov = fields.Char(
        string="Deskline dbOv",
        help="Value of the 'dbOv' query parameter, e.g. MW9. "
        "Auto-filled by 'Log in to Deskline' when discoverable, but can be corrected manually.",
    )
    x_deskline_session_cookies = fields.Text(
        string="Deskline Session Cookies",
        help="JSON cookie array, either pasted from tmp/deskline_cookies.json (see "
        "misc/internal/guestemeldung/deskline_login.py --auto-login) or filled in "
        "automatically by the 'Log in to Deskline' button.",
    )

    def action_deskline_login(self):
        self.ensure_one()
        if not self.x_deskline_username or not self.x_deskline_password:
            raise UserError(self.env._("Set the Deskline username and password first."))
        if not os.path.exists(_PLAYWRIGHT_WORKER_PATH):
            raise UserError(
                self.env._("Deskline Playwright worker script not found: %(path)s", path=_PLAYWRIGHT_WORKER_PATH)
            )

        # Run Playwright in a separate OS process: launching its browser directly
        # inside an Odoo worker thread was observed to crash with
        # TargetClosedError/SIGTRAP, even though the exact same venv launches it
        # fine from a plain interactive shell — the conflict is with the Odoo
        # worker process itself, not a missing dependency.
        request = json.dumps(
            {
                "username": self.x_deskline_username,
                "password": self.x_deskline_password,
                "region": _DESKLINE_REGION,
            }
        )
        try:
            result = subprocess.run(
                [sys.executable, _PLAYWRIGHT_WORKER_PATH],
                input=request,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
                preexec_fn=_reset_child_limits,
                start_new_session=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise UserError(self.env._("Deskline login timed out.")) from exc

        if result.returncode != 0:
            raise UserError(
                self.env._(
                    "Deskline login worker failed: %(stderr)s",
                    stderr=(result.stderr or "unknown error")[-1000:],
                )
            )

        try:
            data = json.loads(result.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError) as exc:
            raise UserError(
                self.env._(
                    "Deskline login worker returned unexpected output: %(output)s",
                    output=result.stdout[-500:],
                )
            ) from exc

        if data.get("error"):
            raise UserError(data["error"])

        self.x_deskline_session_cookies = json.dumps(data["cookies"])
        if data.get("property_id") and data.get("db_ov"):
            self.x_deskline_property_id = data["property_id"]
            self.x_deskline_db_ov = data["db_ov"]

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Deskline"),
                "message": self.env._("Deskline connection verified."),
                "sticky": False,
            },
        }

    def _deskline_request(self, path, query):
        """POST a guest payload to a Deskline visitorregistrationforms endpoint (used for
        both the initial submission and the Voranmeldung->Meldeschein conversion, which
        share the exact same request shape/headers and response envelope) and return the
        parsed JSON body."""
        self.ensure_one()
        try:
            cookies = json.loads(self.x_deskline_session_cookies)
        except ValueError as exc:
            raise UserError(self.env._("Deskline session cookies are not valid JSON.")) from exc
        cookie_header = "; ".join(f"{cookie['name']}={cookie['value']}" for cookie in cookies)

        url = f"{_DESKLINE_BASE_URL}{path}?{query}"
        referer = (
            f"{_DESKLINE_BASE_URL}/{_DESKLINE_REGION}/de/visitorregistrationforms/"
            f"guestregistration/{self.x_deskline_property_id}?dbOv={self.x_deskline_db_ov}"
        )
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": _DESKLINE_BASE_URL,
            "Referer": referer,
            "Cookie": cookie_header,
        }
        return url, headers

    def _submit_deskline_payload(self, payload):
        """Create (or update) a Deskline registration. Returns the parsed response, e.g.
        {"success": true, "masterId": "...", "masterSubType": 0, ...}."""
        self.ensure_one()
        path = f"/{_DESKLINE_REGION}/de/visitorregistrationforms/" f"savevtsheet/{self.x_deskline_property_id}"
        # headerType=7 is what the "Neue Voranmeldung" (Individualgast) form itself
        # submits -- confirmed via a real captured request/response. headerType=0
        # was silently rejected as "Daten ungültig" regardless of payload contents.
        url, headers = self._deskline_request(path, f"dbOv={self.x_deskline_db_ov}&headerType=7&subType=0")
        response = requests.post(url, json={"model": json.dumps(payload)}, headers=headers, timeout=30)
        return self._parse_deskline_response(response, "Deskline submission")

    def _convert_deskline_payload(self, payload, master_id, master_sub_type):
        """Convert an existing Voranmeldung/Meldeschein draft (identified by master_id,
        as returned by a previous _submit_deskline_payload call) into a final numbered
        Meldeschein. Confirmed via a real captured request/response: the endpoint expects
        the same guest payload (with MasterId set to the existing registration) as a POST
        body, not just the query-string parameters."""
        self.ensure_one()
        path = f"/{_DESKLINE_REGION}/de/visitorregistrationforms/convertto/{self.x_deskline_property_id}"
        query = (
            f"dbOv={self.x_deskline_db_ov}&masterId={master_id}"
            f"&convertToType=0&masterSubType={master_sub_type}"
        )
        url, headers = self._deskline_request(path, query)
        response = requests.post(url, json={"model": json.dumps(payload)}, headers=headers, timeout=30)
        return self._parse_deskline_response(response, "Deskline conversion")

    def _parse_deskline_response(self, response, action_label):
        if not response.ok:
            raise UserError(
                self.env._(
                    "%(action)s failed (%(status)s): %(text)s",
                    action=action_label,
                    status=response.status_code,
                    text=response.text[:300],
                )
            )

        # Deskline returns HTTP 200 even for application-level failures, with the
        # real result in the JSON body (e.g. {"success": false, "message": "Daten
        # ungültig"}) -- an ok HTTP status alone does not mean the call worked.
        try:
            result = json.loads(response.text)
        except ValueError:
            result = None
        if isinstance(result, dict) and result.get("success") is False:
            raise UserError(
                self.env._(
                    "%(action)s was rejected: %(message)s",
                    action=action_label,
                    message=result.get("message") or self.env._("no details given"),
                )
            )
        return result
