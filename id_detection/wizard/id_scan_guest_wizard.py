import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IdScanGuestWizard(models.TransientModel):
    _name = "id.scan.guest.wizard"
    _description = "Create a guest from a passport/ID scan"

    order_id = fields.Many2one("sale.order", string="Order", required=True, ondelete="cascade")
    x_id_document_front = fields.Image(string="Document Front")
    x_id_document_back = fields.Image(string="Document Back")

    def action_create_guest(self):
        self.ensure_one()
        if not self.x_id_document_front and not self.x_id_document_back:
            raise UserError(_("Upload a front or back image of the document first."))

        partner = self.env["res.partner"].create(
            {
                "name": _("New Guest"),
                "company_type": "person",
                "x_id_document_front": self.x_id_document_front,
                "x_id_document_back": self.x_id_document_back,
            }
        )

        # Keep the guest even if the scan cannot read the document: the user can
        # still fill the fields manually afterwards.
        try:
            partner.action_scan_id_documents()
        except UserError as error:
            _logger.warning("ID scan failed while creating guest for order %s: %s", self.order_id.name, error)
            partner.message_post(body=_("Document scan failed: %(error)s", error=str(error)))

        self.order_id.x_guest_line_ids = [(0, 0, {"x_guest_partner_id": partner.id})]

        return {"type": "ir.actions.client", "tag": "soft_reload"}
