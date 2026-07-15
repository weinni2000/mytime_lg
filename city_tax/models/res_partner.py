from datetime import date

from odoo import api, fields, models

from ._const import (
    _DESKLINE_SALUTATION_FRAU,
    _DESKLINE_SALUTATION_HERR,
    _GUEST_FIELD_LABELS,
    _GUEST_FULL_REQUIRED_FIELDS,
    _GUEST_LIGHT_REQUIRED_FIELDS,
    _X_ANREDE_SELECTION,
)

_GUEST_CHECK_SELECTION = [("ok", "OK"), ("invalid", "Invalid")]

# Only titles that unambiguously imply a salutation code are mapped;
# gender-neutral titles (Doctor, Professor, ...) are left for manual choice.
_TITLE_NAME_TO_ANREDE = {
    "Mister": _DESKLINE_SALUTATION_HERR,
    "Madam": _DESKLINE_SALUTATION_FRAU,
}


class ResPartner(models.Model):
    _inherit = "res.partner"

    x_document_date = fields.Date(string="Document Date")
    x_document_authority = fields.Char(string="Document Authority")
    x_birthdate = fields.Date(string="Birthdate")
    x_age = fields.Integer(string="Age", compute="_compute_x_age")
    x_marketing_consent = fields.Boolean(string="Marketing Consent")
    x_anrede = fields.Selection(_X_ANREDE_SELECTION, string="Anrede", default=_DESKLINE_SALUTATION_HERR)

    x_guest_data_check = fields.Selection(
        _GUEST_CHECK_SELECTION, string="Guest Data Check", compute="_compute_x_guest_checks"
    )
    x_guest_data_warning = fields.Char(string="Guest Data Warning", compute="_compute_x_guest_checks")
    x_guest_full_data_check = fields.Selection(
        _GUEST_CHECK_SELECTION, string="Main Guest Data Check", compute="_compute_x_guest_checks"
    )
    x_guest_full_data_warning = fields.Char(string="Main Guest Data Warning", compute="_compute_x_guest_checks")
    x_calc_nationality_id = fields.Many2one(
        "res.country",
        string="Calculated Nationality",
        compute="_compute_x_calc_nationality_id",
        store=True,
    )

    @api.depends("x_nationality", "country_id")
    def _compute_x_calc_nationality_id(self):
        for partner in self:
            partner.x_calc_nationality_id = partner.x_nationality or partner.country_id

    @api.onchange("title_id")
    def _onchange_title_id_fill_anrede(self):
        for partner in self:
            anrede = _TITLE_NAME_TO_ANREDE.get(partner.title_id.name)
            if anrede:
                partner.x_anrede = anrede

    @api.depends("x_birthdate")
    def _compute_x_age(self):
        for partner in self:
            if partner.x_birthdate:
                today = date.today()
                partner.x_age = (
                    today.year
                    - partner.x_birthdate.year
                    - ((today.month, today.day) < (partner.x_birthdate.month, partner.x_birthdate.day))
                )
            else:
                partner.x_age = 0

    @api.depends(*_GUEST_FULL_REQUIRED_FIELDS)
    def _compute_x_guest_checks(self):
        for partner in self:
            light_missing = [
                _GUEST_FIELD_LABELS[field_name]
                for field_name in _GUEST_LIGHT_REQUIRED_FIELDS
                if not partner[field_name]
            ]
            partner.x_guest_data_check = "invalid" if light_missing else "ok"
            partner.x_guest_data_warning = "Missing: " + ", ".join(light_missing) if light_missing else False

            full_missing = [
                _GUEST_FIELD_LABELS[field_name]
                for field_name in _GUEST_FULL_REQUIRED_FIELDS
                if not partner[field_name]
            ]
            partner.x_guest_full_data_check = "invalid" if full_missing else "ok"
            partner.x_guest_full_data_warning = "Missing: " + ", ".join(full_missing) if full_missing else False
