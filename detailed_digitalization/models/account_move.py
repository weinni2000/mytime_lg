import json
import logging

from odoo import Command, models
from odoo.exceptions import UserError

from odoo.addons.ai.utils.llm_api_service import LLMApiService

from ._const import (
    DETAILED_DIGITIZE_MODEL,
    DETAILED_DIGITIZE_SCHEMA,
    DETAILED_DIGITIZE_SYSTEM_PROMPT,
    DETAILED_DIGITIZE_USER_PROMPT,
)

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_detailed_digitize(self):
        self.ensure_one()
        attachment_id = self._get_detailed_digitize_attachment()
        lines = self._detailed_digitize_extract_lines(attachment_id)
        self._detailed_digitize_create_lines(lines)
        return True

    def _get_detailed_digitize_attachment(self):
        self.ensure_one()
        attachment_id = self.message_main_attachment_id
        if not attachment_id or attachment_id.mimetype != "application/pdf":
            attachment_id = self.attachment_ids.filtered(
                lambda attachment: attachment.mimetype == "application/pdf"
            )[:1]
        if not attachment_id:
            raise UserError(self.env._("Attach a PDF bill before running the detailed digitization."))
        return attachment_id

    def _detailed_digitize_extract_lines(self, attachment_id):
        self.ensure_one()
        files = [{"mimetype": "application/pdf", "value": attachment_id.datas.decode()}]
        responses = LLMApiService(self.env, provider="openai").request_llm(
            llm_model=DETAILED_DIGITIZE_MODEL,
            system_prompts=[DETAILED_DIGITIZE_SYSTEM_PROMPT],
            user_prompts=[DETAILED_DIGITIZE_USER_PROMPT],
            files=files,
            schema=DETAILED_DIGITIZE_SCHEMA,
            temperature=0,
        )
        if not responses:
            raise UserError(self.env._("ChatGPT did not return any data for this document."))
        try:
            data = json.loads(responses[0])
        except (TypeError, ValueError) as error:
            message = self.env._("ChatGPT did not return valid JSON: %(error)s")
            message = message % {"error": error}
            raise UserError(message) from error
        return data.get("lines") or []

    def _detailed_digitize_create_lines(self, lines):
        self.ensure_one()
        if not lines:
            raise UserError(self.env._("ChatGPT did not find any line items in the attached document."))
        kleinstunternehmer = self.company_id.kleinstunternehmer
        command_list = []
        for line in lines:
            name = (line.get("name") or "").strip()
            product = (line.get("product") or "").strip()
            label = f"{name} - {product}" if name and product else name or product
            price_unit = line.get("price") or 0.0
            if kleinstunternehmer:
                # Kleinstunternehmer companies cannot deduct input VAT, so each
                # line's own printed tax rate grosses up its net price to the
                # amount the company actually has to bear.
                price_unit *= 1 + (line.get("tax") or 0.0) / 100
            command_list.append(
                Command.create(
                    {
                        "name": label,
                        "quantity": line.get("amount") or 0.0,
                        "price_unit": price_unit,
                    }
                )
            )
        self.invoice_line_ids = command_list
