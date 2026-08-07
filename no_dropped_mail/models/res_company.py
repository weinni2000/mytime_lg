import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    no_dropped_mail_enabled = fields.Boolean(
        string="Catch Dropped Mails",
        default=True,
        help="When enabled, incoming e-mails that match no alias (and would "
        "otherwise be dropped by Odoo) are posted into a dedicated Discuss "
        "channel instead of being lost.",
    )
    no_dropped_mail_channel_id = fields.Many2one(
        comodel_name="discuss.channel",
        string="Dropped Mail Channel",
        help="Discuss channel collecting incoming e-mails that could not be "
        "routed to any alias. Created automatically on first use.",
    )

    def _get_no_dropped_mail_channel(self):
        """Return the Discuss channel collecting unroutable incoming mail for
        this company, creating it on first use and keeping all internal users
        as members.
        """
        self.ensure_one()
        channel = self.sudo().no_dropped_mail_channel_id
        if not channel:
            channel = (
                self.env["discuss.channel"]
                .sudo()
                .create(
                    {
                        "name": _("Dropped Mails"),
                        "channel_type": "channel",
                        "description": _(
                            "Incoming e-mails that matched no alias and would "
                            "have been dropped are collected here."
                        ),
                    }
                )
            )
            self.sudo().no_dropped_mail_channel_id = channel.id
            _logger.info(
                "no_dropped_mail: created collector channel %s for company %s",
                channel.id,
                self.id,
            )
        self._sync_no_dropped_mail_members(channel)
        return channel

    def _sync_no_dropped_mail_members(self, channel):
        """Ensure every active internal user is a member of the channel."""
        internal_partners = (
            self.env["res.users"].sudo().search([("share", "=", False), ("active", "=", True)]).partner_id
        )
        missing = internal_partners - channel.channel_partner_ids
        if missing:
            channel.add_members(partner_ids=missing.ids, post_joined_message=False)
