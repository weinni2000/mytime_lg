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
        "submission. Passed back on a later resubmission to update this same "
        "registration instead of creating a new one.",
    )
    x_feratel_number = fields.Char(
        string="Feratel Number",
        copy=False,
        help="Registration/Meldeschein number shown for this record in Feratel's own "
        "Deskline portal. Not returned by the submission API (which only ever returns "
        "the masterId), so this is entered manually after checking the Feratel portal.",
    )

    def _get_deskline_guest_lines(self):
        """Return the x_guests_line records to submit."""
        raise NotImplementedError

    def _get_deskline_company(self):
        return self.env.company

    def action_send_to_deskline(self):
        force_resend = self.env.context.get("deskline_force_resend")
        if len(self) == 1 and self.x_deskline_master_id and not force_resend:
            return self._deskline_resend_confirm_action()

        to_send = self if force_resend else self.filtered(lambda record: not record.x_deskline_master_id)
        already_transferred = self - to_send
        for record in to_send:
            record._send_guests_to_deskline()
            # Commit after every record: if a later record's submission raises, the
            # default rollback would otherwise also discard the masterId already
            # written for records that succeeded earlier in this loop.
            self.env.cr.commit()  # pylint: disable=invalid-commit

        if already_transferred:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": self.env._("Deskline"),
                    "message": self.env._(
                        "Skipped %(count)s record(s) already transferred to Deskline: %(names)s",
                        count=len(already_transferred),
                        names=", ".join(already_transferred.mapped("display_name")),
                    ),
                    "type": "warning",
                    "sticky": True,
                },
            }
        return None

    def _deskline_resend_confirm_action(self):
        self.ensure_one()
        wizard = self.env["guest.tax.deskline.resend.wizard"].create({"res_model": self._name, "res_id": self.id})
        return {
            "type": "ir.actions.act_window",
            "res_model": "guest.tax.deskline.resend.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def _deskline_guest_lines_or_raise(self):
        self.ensure_one()
        guest_lines = self._get_deskline_guest_lines()
        if not guest_lines:
            raise UserError(self.env._("There are no guests to submit."))
        included_guest_lines = guest_lines.filtered(lambda guest_line: not guest_line.x_manual_exclude)
        if not included_guest_lines:
            raise UserError(
                self.env._("All guests are manually excluded. There is no guest tax information to send.")
            )
        return included_guest_lines

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
        return result
