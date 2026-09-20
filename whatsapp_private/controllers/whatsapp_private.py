import hmac
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WhatsAppPrivateController(http.Controller):
    @http.route(
        "/whatsapp_private/notify_inbox",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def notify_inbox(self, company_id=None, token=None, **kwargs):
        """Called by the local WhatsApp worker the instant it queues a new
        message (sent or received), so it reaches Discuss immediately
        instead of waiting for the next 'Private WhatsApp: Receive
        Messages' cron tick (up to a minute later, longer under load).

        Authenticated with a per-company secret (see
        ResCompany._whatsapp_private_notify_token) rather than a user
        session, since the worker is a local background process with no
        Odoo login. On any mismatch this just no-ops; the cron remains the
        fallback so a failed/blocked call never loses a message.
        """
        try:
            company_id = int(company_id)
        except (TypeError, ValueError):
            return {"ok": False}
        company = request.env["res.company"].sudo().browse(company_id).exists()
        if not company:
            return {"ok": False}
        expected_token = company._whatsapp_private_notify_token()
        if not token or not hmac.compare_digest(str(token), expected_token):
            _logger.warning("WhatsApp private notify: rejected invalid token for company %s.", company_id)
            return {"ok": False}
        account = (
            request.env["whatsapp.account"]
            .sudo()
            .search(
                [
                    ("private_company_id", "=", company.id),
                    ("connection_type", "=", "private"),
                    ("active", "=", True),
                ],
                limit=1,
            )
        )
        if not account:
            return {"ok": False}
        account._process_private_inbox()
        return {"ok": True}
