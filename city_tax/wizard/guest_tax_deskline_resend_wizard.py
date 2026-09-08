from odoo import fields, models


class GuestTaxDesklineResendWizard(models.TransientModel):
    _name = "guest.tax.deskline.resend.wizard"
    _description = "Confirm Deskline Resubmission"

    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    record_display_name = fields.Char(compute="_compute_record_display_name")

    def _compute_record_display_name(self):
        for wizard in self:
            wizard.record_display_name = self.env[wizard.res_model].browse(wizard.res_id).display_name

    def action_resend(self):
        self.ensure_one()
        record = self.env[self.res_model].browse(self.res_id)
        return record.with_context(deskline_force_resend=True).action_send_to_deskline()
