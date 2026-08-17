import json
import logging
import re

from odoo import _, http
from odoo.http import request

from ..sms import extract_booking_code

_logger = logging.getLogger(__name__)


class BookingManual(http.Controller):
    @http.route("/booking/novnc/auth", type="http", auth="public", methods=["GET"], csrf=False)
    def authorize_booking_novnc(self):
        if not request.env.user.has_group("base.group_system"):
            return request.make_response("Forbidden", status=403)
        return request.make_response("", status=204)

    @http.route(
        "/booking/key",
        type="json2",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def receive_booking_key(self, **post):
        raw_body = request.httprequest.get_data(as_text=True)
        json_payload = {}
        json_error = False
        if request.httprequest.is_json and raw_body:
            try:
                parsed_payload = json.loads(raw_body)
                if isinstance(parsed_payload, dict):
                    json_payload = parsed_payload
                else:
                    json_error = True
            except (TypeError, ValueError):
                json_error = True
                _logger.warning("Booking webhook received an invalid JSON body.")

        diagnostic_args = request.httprequest.args.to_dict(flat=False)
        diagnostic_form = request.httprequest.form.to_dict(flat=False)
        for payload in (diagnostic_args, diagnostic_form):
            if "key" in payload:
                payload["key"] = ["<redacted>"]
        diagnostic_body = raw_body[:4000]
        diagnostic_body = re.sub(
            r'(?i)(["\']?key["\']?\s*[:=]\s*["\']?)[^&"\'\s}]+',
            r"\1<redacted>",
            diagnostic_body,
        )
        diagnostic_body = re.sub(r"\b\d{4,8}\b", "<verification-code>", diagnostic_body)
        diagnostic_headers = dict(request.httprequest.headers)
        for header_name in list(diagnostic_headers):
            if header_name.lower() in ("authorization", "cookie", "key", "x-api-key", "x-booking-key"):
                diagnostic_headers[header_name] = "<redacted>"
        _logger.warning(
            "Booking webhook received: method=%s content_type=%s is_json=%s "
            "json_error=%s args=%r form=%r json_fields=%s post_fields=%s "
            "body=%r headers=%r",
            request.httprequest.method,
            request.httprequest.content_type,
            request.httprequest.is_json,
            json_error,
            diagnostic_args,
            diagnostic_form,
            sorted(json_payload),
            sorted(post),
            diagnostic_body,
            diagnostic_headers,
        )
        payload = dict(json_payload)
        payload.update(post)
        header_key = request.httprequest.headers.get("Key")
        key_source = "payload" if payload.get("key") else "header" if header_key else "missing"
        key = str(payload.get("key") or header_key or "").strip()
        message_field = next(
            (name for name in ("nachricht", "message", "body", "text") if payload.get(name)),
            None,
        )
        message = payload.get(message_field) if message_field else ""
        message = str(message).strip()
        _logger.warning(
            "Booking webhook parsed: key_source=%s key_present=%s message_field=%s " "message_length=%s",
            key_source,
            bool(key),
            message_field,
            len(message),
        )
        if not key:
            _logger.warning("Booking webhook rejected: missing key.")
            return request.make_json_response({"error": _("Missing key.")}, status=400)
        code = extract_booking_code(message)
        if not code:
            _logger.warning(
                "Booking webhook rejected: no verification code found (message_field=%s, " "message_length=%s).",
                message_field,
                len(message),
            )
            return request.make_json_response(
                {"error": _("No verification code found in message.")},
                status=422,
            )

        booking_account_id = request.env["booking.account"].sudo().create({"temp_booking_key": code})
        _logger.warning(
            "Booking webhook accepted: code_length=%s stored_on_booking_account=%s.",
            len(code),
            booking_account_id.id,
        )
        return request.make_json_response({"id": booking_account_id.id})
