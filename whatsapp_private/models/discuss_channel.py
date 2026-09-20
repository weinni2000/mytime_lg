from datetime import datetime

from odoo import models

from odoo.addons.mail.tools.discuss import Store


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)
        if len(self) == 1 and self.channel_type == "whatsapp":
            self._whatsapp_silence_notifications(message)
        return message

    def _whatsapp_silence_notifications(self, message):
        """WhatsApp channels must never pop a chat window/bubble or play a
        notification sound on send or receive. Messages stay fully visible
        (normal history, normal sidebar entry, normal unread counter logic)
        - only the popup is silenced: members are muted forever (the native
        Discuss "Mute Conversation" mechanism, so the client-side ChatHub
        code never even considers this channel) and the new message is
        marked as read immediately so it doesn't linger as unread either."""
        self.ensure_one()
        if not message:
            return
        members = self.channel_member_ids
        members.filtered(lambda member: member.mute_until_dt != datetime.max).write(
            {"mute_until_dt": datetime.max}
        )
        for member in members:
            member._mark_as_read(message.id)

    def _whatsapp_private_muted(self):
        account = self.wa_account_id
        if account.connection_type != "private":
            return False
        return account.private_company_id.whatsapp_private_mute_notifications

    def _to_store_defaults(self, target):
        return super()._to_store_defaults(target) + [
            Store.Attr(
                "whatsapp_auto_open_chat_window",
                value=lambda channel: channel.wa_account_id.auto_open_chat_window
                and not channel._whatsapp_private_muted(),
                predicate=lambda channel: channel.channel_type == "whatsapp",
                sudo=True,
            ),
        ]
