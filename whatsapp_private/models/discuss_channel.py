from odoo import models

from odoo.addons.mail.tools.discuss import Store


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _to_store_defaults(self, target):
        return super()._to_store_defaults(target) + [
            Store.Attr(
                "whatsapp_auto_open_chat_window",
                value=lambda channel: channel.wa_account_id.auto_open_chat_window,
                predicate=lambda channel: channel.channel_type == "whatsapp",
                sudo=True,
            ),
        ]
