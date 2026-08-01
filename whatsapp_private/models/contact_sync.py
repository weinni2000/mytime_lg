import json
import os
import time
import uuid

from odoo import _, api, fields, models
from odoo.exceptions import UserError


# pylint: disable=consider-merging-classes-inherited
class ResCompany(models.Model):
    _inherit = "res.company"

    whatsapp_private_contacts_last_sync = fields.Datetime(string="Last WhatsApp Contact Sync", readonly=True)
    whatsapp_private_contacts_count = fields.Integer(string="WhatsApp Contacts", readonly=True)
    whatsapp_private_contacts_sync_detail = fields.Text(string="Contact Sync Result", readonly=True)
    whatsapp_private_contacts_auto_sync = fields.Boolean(
        string="Automatic Nightly WhatsApp Contact Sync",
        help="After the initial reviewed import, update and import WhatsApp contacts nightly.",
    )
    whatsapp_private_odoo_contacts_last_sync = fields.Datetime(string="Last Odoo to WhatsApp Sync", readonly=True)
    whatsapp_private_odoo_contacts_sync_detail = fields.Text(string="Odoo to WhatsApp Result", readonly=True)

    def _whatsapp_private_request_contact_snapshot(self, timeout=20):
        self.ensure_one()
        directory = self._whatsapp_private_directory()
        if not self._whatsapp_private_worker_pids(("listen",)):
            raise UserError(_("The WhatsApp listener is not running. Reconnect or wait for the listener cron."))
        request_id = uuid.uuid4().hex
        request_path = directory / "contact_export.request"
        temporary = request_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"request_id": request_id, "requested_at": time.time()}), encoding="utf-8")
        os.replace(temporary, request_path)
        snapshot_path = directory / "contacts_snapshot.json"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                time.sleep(0.2)
                continue
            if snapshot.get("request_id") == request_id:
                if snapshot.get("error"):
                    raise UserError(_("WhatsApp contact export failed: %s", snapshot["error"]))
                return snapshot
            time.sleep(0.2)
        raise UserError(_("WhatsApp contact export timed out. Please retry."))

    def _whatsapp_private_push_contacts(self, partners, timeout=30):
        self.ensure_one()
        directory = self._whatsapp_private_directory()
        state = self._read_whatsapp_private_state()
        heartbeat = directory / "heartbeat"
        listener_connected = (
            state.get("status") == "connected"
            and heartbeat.exists()
            and time.time() - heartbeat.stat().st_mtime < 20
        )
        if not listener_connected:
            raise UserError(_("WhatsApp is not connected for %s. Link that company first.", self.display_name))
        contacts = {}
        for partner in partners.sudo():
            phone = "".join(
                character for character in (partner.phone_sanitized or partner.phone or "") if character.isdigit()
            )
            if not phone or not partner.name:
                continue
            contacts[phone] = {
                "partner_id": partner.id,
                "phone": phone,
                "name": partner.name.strip(),
                "first_name": partner.name.strip().split()[0],
            }
        if not contacts:
            raise UserError(_("No selected Odoo contact has a valid international phone number."))
        request_id = uuid.uuid4().hex
        request_path = directory / "contact_update.request"
        temporary = request_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"request_id": request_id, "contacts": list(contacts.values())}),
            encoding="utf-8",
        )
        os.replace(temporary, request_path)
        result_path = directory / "contact_update_result.json"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                time.sleep(0.2)
                continue
            if result.get("request_id") == request_id:
                if result.get("error"):
                    raise UserError(_("Odoo to WhatsApp contact sync failed: %s", result["error"]))
                synced = partners.sudo().filtered(
                    lambda partner: "".join(
                        character
                        for character in (partner.phone_sanitized or partner.phone or "")
                        if character.isdigit()
                    )
                    in contacts
                )
                now = fields.Datetime.now()
                for partner in synced:
                    phone = "".join(
                        character
                        for character in (partner.phone_sanitized or partner.phone or "")
                        if character.isdigit()
                    )
                    values = {
                        "whatsapp_private_company_id": self.id,
                        "whatsapp_private_jid": partner.whatsapp_private_jid or f"{phone}@s.whatsapp.net",
                        "whatsapp_private_outbound_last_sync": now,
                        "whatsapp_private_outbound_sync_status": "synced",
                    }
                    partner.write(values)
                self.sudo().write(
                    {
                        "whatsapp_private_odoo_contacts_last_sync": now,
                        "whatsapp_private_odoo_contacts_sync_detail": _(
                            "Updated %s linked WhatsApp contact names.", result.get("count", 0)
                        ),
                    }
                )
                return result
            time.sleep(0.2)
        raise UserError(_("Odoo to WhatsApp contact sync timed out. Please retry."))

    def action_whatsapp_private_push_odoo_contacts(self):
        self.ensure_one()
        partners = (
            self.env["res.partner"]
            .sudo()
            .search(
                [
                    ("active", "=", True),
                    ("company_id", "in", [False, self.id]),
                    ("phone_sanitized", "!=", False),
                ]
            )
        )
        result = self._whatsapp_private_push_contacts(partners, timeout=60)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Odoo contacts synchronized to WhatsApp"),
                "message": _("Updated %s linked WhatsApp contact names.", result.get("count", 0)),
                "type": "success",
                "sticky": False,
            },
        }

    def _whatsapp_private_contact_match(self, contact):
        self.ensure_one()
        Partner = self.env["res.partner"].sudo().with_context(active_test=False)
        jid = contact.get("jid")
        if jid:
            matches = Partner.search([("whatsapp_private_jid", "=", jid)], limit=2)
            if len(matches) == 1:
                return matches, "jid"
            if len(matches) > 1:
                return Partner, "ambiguous"
        phone = "".join(character for character in contact.get("phone", "") if character.isdigit())
        if phone:
            matches = Partner.search([("phone_sanitized", "in", [phone, "+" + phone])], limit=2)
            if len(matches) == 1:
                return matches, "phone"
            if len(matches) > 1:
                return Partner, "ambiguous"
        return Partner, "new"

    def _whatsapp_private_contact_name(self, contact):
        return (
            contact.get("full_name")
            or contact.get("business_name")
            or contact.get("push_name")
            or contact.get("first_name")
            or "+" + contact.get("phone", "")
        )

    def _whatsapp_private_import_contact(self, contact, partner=False):
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()
        phone_field = "mobile" if "mobile" in Partner._fields else "phone"
        values = {
            "whatsapp_private_jid": contact.get("jid"),
            "whatsapp_private_company_id": self.id,
            "whatsapp_private_first_name": contact.get("first_name"),
            "whatsapp_private_full_name": contact.get("full_name"),
            "whatsapp_private_push_name": contact.get("push_name"),
            "whatsapp_private_business_name": contact.get("business_name"),
            "whatsapp_private_last_sync": fields.Datetime.now(),
            "whatsapp_private_sync_source": "contact_store",
        }
        values = {key: value for key, value in values.items() if value is not None}
        if partner:
            if not partner[phone_field] and contact.get("phone"):
                values[phone_field] = "+" + contact["phone"]
            if not partner.name or partner.name.strip() in {"/", "Unknown"}:
                values["name"] = self._whatsapp_private_contact_name(contact)
            partner.write(values)
            return partner
        values.update(
            {
                "name": self._whatsapp_private_contact_name(contact),
                phone_field: "+" + contact["phone"] if contact.get("phone") else False,
                "company_type": "person",
            }
        )
        return Partner.create(values)

    def _whatsapp_private_import_snapshot(self, snapshot):
        self.ensure_one()
        result = {"created": 0, "updated": 0, "ambiguous": 0, "skipped": 0}
        for contact in snapshot.get("contacts", []):
            if not contact.get("jid") or not contact.get("phone"):
                result["skipped"] += 1
                continue
            partner, status = self._whatsapp_private_contact_match(contact)
            if status == "ambiguous":
                result["ambiguous"] += 1
                continue
            self._whatsapp_private_import_contact(contact, partner=partner)
            result["updated" if partner else "created"] += 1
        self.write(
            {
                "whatsapp_private_contacts_last_sync": fields.Datetime.now(),
                "whatsapp_private_contacts_count": len(snapshot.get("contacts", [])),
                "whatsapp_private_contacts_sync_detail": _(
                    "Created: %(created)s, updated: %(updated)s, ambiguous: %(ambiguous)s, skipped: %(skipped)s",
                    **result,
                ),
            }
        )
        return result

    def action_whatsapp_private_preview_contacts(self):
        self.ensure_one()
        snapshot = self._whatsapp_private_request_contact_snapshot()
        wizard = self.env["whatsapp.contact.sync.wizard"].create_from_snapshot(self, snapshot)
        return {
            "type": "ir.actions.act_window",
            "name": _("Synchronize WhatsApp Contacts"),
            "res_model": "whatsapp.contact.sync.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    @api.model
    def _cron_whatsapp_private_contact_sync(self):
        accounts = (
            self.env["whatsapp.account"]
            .sudo()
            .search([("connection_type", "=", "private"), ("active", "=", True)])
        )
        companies = accounts.mapped("private_company_id").filtered("whatsapp_private_contacts_auto_sync")
        for company in companies:
            try:
                snapshot = company._whatsapp_private_request_contact_snapshot(timeout=30)
                company._whatsapp_private_import_snapshot(snapshot)
                self.env.cr.commit()  # pylint: disable=invalid-commit
            except Exception as exc:
                company.whatsapp_private_contacts_sync_detail = _("Sync failed: %s", exc)
                self.env.cr.commit()  # pylint: disable=invalid-commit
