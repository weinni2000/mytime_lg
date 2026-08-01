from odoo import _, fields, models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    whatsapp_private_jid = fields.Char(
        string="WhatsApp JID",
        index=True,
        copy=False,
        help="Technical WhatsApp linked-device identifier for this contact.",
    )
    whatsapp_private_company_id = fields.Many2one("res.company", string="WhatsApp Company", index=True, copy=False)
    whatsapp_private_first_name = fields.Char(string="WhatsApp First Name", copy=False)
    whatsapp_private_full_name = fields.Char(string="WhatsApp Full Name", copy=False)
    whatsapp_private_push_name = fields.Char(string="WhatsApp Push Name", copy=False)
    whatsapp_private_business_name = fields.Char(string="WhatsApp Business Name", copy=False)
    whatsapp_private_last_sync = fields.Datetime(string="Last WhatsApp Sync", copy=False)
    whatsapp_private_sync_source = fields.Selection(
        [("inbound", "Inbound Message"), ("contact_store", "WhatsApp Contact Store")],
        string="WhatsApp Sync Source",
        copy=False,
    )
    whatsapp_private_outbound_last_sync = fields.Datetime(string="Last Odoo to WhatsApp Sync", copy=False)
    whatsapp_private_outbound_sync_status = fields.Selection(
        [("synced", "Synchronized"), ("error", "Error")],
        string="Odoo to WhatsApp Status",
        copy=False,
    )

    def _whatsapp_private_target_company(self):
        self.ensure_one()
        Account = self.env["whatsapp.account"].sudo()
        candidates = self.whatsapp_private_company_id or self.company_id or self.env.company
        if candidates and Account.search_count(
            [
                ("connection_type", "=", "private"),
                ("private_company_id", "=", candidates.id),
                ("active", "=", True),
            ]
        ):
            return candidates
        raise UserError(_("No active private WhatsApp account is configured for the contact or active company."))

    def action_whatsapp_private_sync_to_linked_contacts(self):
        grouped = {}
        for partner in self:
            company = partner._whatsapp_private_target_company()
            grouped.setdefault(company.id, self.env["res.partner"])
            grouped[company.id] |= partner
        total = 0
        for company_id, partners in grouped.items():
            result = (
                self.env["res.company"]
                .sudo()
                .browse(company_id)
                ._whatsapp_private_push_contacts(partners, timeout=30)
            )
            total += result.get("count", 0)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Contact synchronized to WhatsApp"),
                "message": _("Updated %s linked WhatsApp contact name(s).", total),
                "type": "success",
                "sticky": False,
            },
        }
