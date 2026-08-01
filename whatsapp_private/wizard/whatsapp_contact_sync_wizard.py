from odoo import _, api, fields, models


class WhatsAppContactSyncWizard(models.TransientModel):
    _name = "whatsapp.contact.sync.wizard"
    _description = "Preview WhatsApp Contact Synchronization"

    company_id = fields.Many2one("res.company", required=True, readonly=True)
    line_ids = fields.One2many("whatsapp.contact.sync.wizard.line", "wizard_id")
    contact_count = fields.Integer(readonly=True)
    new_count = fields.Integer(readonly=True)
    matched_count = fields.Integer(readonly=True)
    ambiguous_count = fields.Integer(readonly=True)

    @api.model
    def create_from_snapshot(self, company, snapshot):
        commands = []
        counts = {"new": 0, "matched": 0, "ambiguous": 0}
        for contact in snapshot.get("contacts", []):
            partner, match = company._whatsapp_private_contact_match(contact)
            status = "matched_" + match if match in {"jid", "phone"} else match
            counts["matched" if status.startswith("matched_") else status] += 1
            commands.append(
                fields.Command.create(
                    {
                        "selected": status != "ambiguous",
                        "status": status,
                        "matched_partner_id": partner.id,
                        "partner_display_name": partner.sudo().display_name if partner else "",
                        "phone": contact.get("phone"),
                        "jid": contact.get("jid"),
                        "proposed_name": company._whatsapp_private_contact_name(contact),
                        "full_name": contact.get("full_name"),
                        "business_name": contact.get("business_name"),
                        "push_name": contact.get("push_name"),
                        "contact_data": contact,
                    }
                )
            )
        return self.create(
            {
                "company_id": company.id,
                "line_ids": commands,
                "contact_count": len(snapshot.get("contacts", [])),
                "new_count": counts["new"],
                "matched_count": counts["matched"],
                "ambiguous_count": counts["ambiguous"],
            }
        )

    def action_import(self):
        self.ensure_one()
        wizard = self.sudo()
        result = {"created": 0, "updated": 0, "skipped": 0}
        for line in wizard.line_ids:
            if not line.selected or (
                line.status == "ambiguous" and not line.partner_id and not line.matched_partner_id
            ):
                result["skipped"] += 1
                continue
            partner = line.partner_id.sudo() or self.env["res.partner"].sudo().browse(line.matched_partner_id)
            was_existing = bool(partner)
            self.company_id.sudo()._whatsapp_private_import_contact(line.contact_data, partner=partner)
            result["updated" if was_existing else "created"] += 1
        self.company_id.sudo().write(
            {
                "whatsapp_private_contacts_last_sync": fields.Datetime.now(),
                "whatsapp_private_contacts_count": self.contact_count,
                "whatsapp_private_contacts_sync_detail": _(
                    "Created: %(created)s, updated: %(updated)s, skipped: %(skipped)s", **result
                ),
            }
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("WhatsApp contacts synchronized"),
                "message": self.company_id.whatsapp_private_contacts_sync_detail,
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }


class WhatsAppContactSyncWizardLine(models.TransientModel):
    _name = "whatsapp.contact.sync.wizard.line"
    _description = "WhatsApp Contact Synchronization Preview Line"
    _order = "status, proposed_name"

    wizard_id = fields.Many2one("whatsapp.contact.sync.wizard", required=True, ondelete="cascade")
    selected = fields.Boolean(default=True)
    status = fields.Selection(
        [
            ("new", "Create"),
            ("matched_jid", "Match: WhatsApp ID"),
            ("matched_phone", "Match: Phone"),
            ("ambiguous", "Review: Ambiguous"),
        ],
        required=True,
        readonly=True,
    )
    matched_partner_id = fields.Integer(readonly=True)
    partner_display_name = fields.Char(string="Matched Odoo Contact", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Choose Odoo Contact")
    proposed_name = fields.Char(readonly=True)
    phone = fields.Char(readonly=True)
    jid = fields.Char(readonly=True)
    full_name = fields.Char(readonly=True)
    business_name = fields.Char(readonly=True)
    push_name = fields.Char(readonly=True)
    contact_data = fields.Json(readonly=True)
