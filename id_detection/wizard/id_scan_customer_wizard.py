from odoo import _, fields, models
from odoo.exceptions import UserError


class IdScanCustomerWizard(models.TransientModel):
    _name = "id.scan.customer.wizard"
    _description = "Create a customer from a passport/ID scan"

    order_id = fields.Many2one("sale.order", string="Order", ondelete="cascade")
    x_id_document_front = fields.Image(string="Document Front", required=True)
    x_id_document_back = fields.Image(string="Document Back", required=True)

    def action_create_customer(self):
        self.ensure_one()
        if not self.x_id_document_front or not self.x_id_document_back:
            raise UserError(_("Upload the front and back images of the document first."))

        partner_id = self.env["res.partner"].create(
            {
                "name": _("New Customer"),
                "company_type": "person",
                "x_id_document_front": self.x_id_document_front,
                "x_id_document_back": self.x_id_document_back,
            }
        )

        partner_id.action_scan_id_documents()
        if partner_id.name == _("New Customer"):
            raise UserError(_("Document scan did not read a customer name. No customer was assigned."))

        if self.order_id:
            self.order_id.partner_id = partner_id.id
            return {"type": "ir.actions.client", "tag": "soft_reload"}

        order_id = self.env["sale.order"].create(
            {
                "partner_id": partner_id.id,
                "is_rental_order": True,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Rental Order"),
            "res_model": "sale.order",
            "res_id": order_id.id,
            "view_mode": "form",
            "views": [(self.env.ref("sale_renting.rental_order_primary_form_view").id, "form")],
            "target": "current",
            "context": {"in_rental_app": 1},
        }
