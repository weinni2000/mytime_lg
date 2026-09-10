from odoo import models

from odoo.addons.mail.tools.discuss import Store


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

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
