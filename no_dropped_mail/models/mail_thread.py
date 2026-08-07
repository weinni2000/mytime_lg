import logging

from odoo import api, models
from odoo.tools import email_split

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    @api.model
    def _no_dropped_mail_company(self, message_dict):
        """Resolve which company should collect a dropped mail.

        Match the recipient address domain against each company's alias
        domain and return that company; fall back to the environment's
        default company when no domain matches.
        """
        recipients = email_split(",".join((message_dict.get("to") or "", message_dict.get("recipients") or "")))
        domains = {rcpt.split("@", 1)[1].lower() for rcpt in recipients if "@" in rcpt}
        if domains:
            companies = self.env["res.company"].sudo().search([("alias_domain_id", "!=", False)])
            for company in companies:
                if company.alias_domain_id.name.lower() in domains:
                    return company
        return self.env.company

    @api.model
    def message_route(self, message, message_dict, model=None, thread_id=None, custom_values=None):
        """Fallback unroutable incoming e-mails to a Discuss channel.

        Odoo drops an incoming e-mail by raising a ``ValueError`` at the end of
        the standard :meth:`message_route` when it matches no alias, no reply
        thread and no fallback model. When the feature is enabled on the
        company we catch that case and route the message to a dedicated Discuss
        channel instead, so the mail is preserved rather than lost.
        """
        try:
            return super().message_route(
                message,
                message_dict,
                model=model,
                thread_id=thread_id,
                custom_values=custom_values,
            )
        except ValueError as err:
            # Only the "no route found" drop is caught; other ValueErrors
            # (e.g. a malformed alias_defaults) must keep propagating.
            if "No possible route found" not in str(err):
                raise
            company = self._no_dropped_mail_company(message_dict)
            if not company.no_dropped_mail_enabled:
                raise
            channel = company._get_no_dropped_mail_channel()
            if not channel:
                raise
            email_from = message_dict.get("email_from")
            user_id = self._mail_find_user_for_gateway(email_from).id or self.env.uid
            _logger.info(
                "no_dropped_mail: routing unroutable mail from %s to %s "
                "(Message-Id %s) into Discuss channel %s",
                email_from,
                message_dict.get("to"),
                message_dict.get("message_id"),
                channel.id,
            )
            # (model, thread_id, custom_values, user_id, alias); a truthy
            # thread_id on a mail.thread model makes _message_route_process
            # post the full e-mail (body, subject, attachments) as a message.
            return [("discuss.channel", channel.id, {}, user_id, None)]
