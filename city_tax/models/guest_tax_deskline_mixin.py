from odoo import fields, models
from odoo.exceptions import UserError

from . import _deskline_utils


class GuestTaxDesklineMixin(models.AbstractModel):
    _name = "guest.tax.deskline.mixin"
    _description = "Deskline Submission Mixin"

    x_deskline_master_id = fields.Char(
        string="Deskline Reference",
        readonly=True,
        copy=False,
        help="masterId of this registration on Deskline, returned by the initial "
        "submission. Needed to later convert a Voranmeldung into a final Meldeschein.",
    )
    x_deskline_master_sub_type = fields.Integer(string="Deskline Reference Sub Type", readonly=True, copy=False)

    def _get_deskline_guest_lines(self):
        """Return the guest-line recordset (x_guests_line or y_guests_line) to submit."""
        raise NotImplementedError

    def _get_deskline_company(self):
        return self.env.company

    def action_send_to_deskline(self):
        for record in self:
            record._send_guests_to_deskline()

    def action_convert_to_meldeschein(self):
        for record in self:
            record._convert_guests_to_deskline()

    def _deskline_guest_lines_or_raise(self):
        self.ensure_one()
        guest_lines = self._get_deskline_guest_lines()
        if not guest_lines:
            raise UserError(self.env._("There are no guests to submit."))
        return guest_lines

    def _deskline_company_or_raise(self):
        self.ensure_one()
        company = self._get_deskline_company()
        if not company.x_deskline_session_cookies:
            raise UserError(
                self.env._(
                    "No Deskline session cookies stored on the company. Run "
                    "misc/internal/guestemeldung/deskline_login.py --auto-login and paste "
                    "tmp/deskline_cookies.json into the company's Deskline settings."
                )
            )
        return company

    def _send_guests_to_deskline(self):
        self.ensure_one()
        company = self._deskline_company_or_raise()
        guest_lines = self._deskline_guest_lines_or_raise()

        kwargs = {"master_id": self.x_deskline_master_id} if self.x_deskline_master_id else {}
        payload = _deskline_utils.build_submission_payload(guest_lines, **kwargs)
        result = company._submit_deskline_payload(payload)
        if isinstance(result, dict) and result.get("masterId"):
            self.x_deskline_master_id = result["masterId"]
            self.x_deskline_master_sub_type = result.get("masterSubType") or 0
        return result

    def _convert_guests_to_deskline(self):
        self.ensure_one()
        if not self.x_deskline_master_id:
            raise UserError(self.env._("This has not been sent to Deskline yet — use 'Send to Deskline' first."))
        company = self._deskline_company_or_raise()
        guest_lines = self._deskline_guest_lines_or_raise()

        payload = _deskline_utils.build_submission_payload(guest_lines, master_id=self.x_deskline_master_id)
        return company._convert_deskline_payload(
            payload, self.x_deskline_master_id, self.x_deskline_master_sub_type
        )
