import unicodedata
from datetime import date

import gender_guesser.detector as gender_detector

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ._const import (
    _DESKLINE_SALUTATION_DAMEN_UND_HERREN,
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

# Loading the name database is the expensive part, so keep a single detector
# for the process rather than one per compute call.
_GENDER_DETECTOR = gender_detector.Detector(case_sensitive=False)
_GENDER_GUESS_TO_ANREDE = {
    "male": _DESKLINE_SALUTATION_HERR,
    "mostly_male": _DESKLINE_SALUTATION_HERR,
    "female": _DESKLINE_SALUTATION_FRAU,
    "mostly_female": _DESKLINE_SALUTATION_FRAU,
}


def _strip_diacritics(text):
    """gender_guesser's name database is plain ASCII, so an accented name
    like "Šimon" or "Jörg" misses entirely unless normalized first."""
    return "".join(char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char))


class ResPartner(models.Model):
    _inherit = "res.partner"

    x_document_date = fields.Date(string="Document Date")
    x_document_authority = fields.Char(string="Document Authority")
    x_manual_age = fields.Integer(string="Manual Age")
    x_age = fields.Integer(string="Age", compute="_compute_x_age")
    x_underage_manual = fields.Boolean(string="Underage (Manual)")
    x_underage = fields.Boolean(string="Underage", compute="_compute_x_age")
    x_taxable = fields.Boolean(string="Taxable", compute="_compute_x_age")
    x_marketing_consent = fields.Boolean(string="Marketing Consent")
    x_anrede = fields.Selection(_X_ANREDE_SELECTION, string="Anrede", default=_DESKLINE_SALUTATION_HERR)
    x_anrede_calc_refresh = fields.Boolean(
        string="Refresh", help="Toggle to force the calculated Anrede to recompute."
    )
    x_anrede_calc = fields.Selection(
        _X_ANREDE_SELECTION, string="Anrede (Calculated)", compute="_compute_x_anrede_calc"
    )

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

    @api.constrains("birthdate_date")
    def _check_birthdate_date_not_future(self):
        for partner in self:
            if partner.birthdate_date and partner.birthdate_date > date.today():
                raise ValidationError(self.env._("Birthdate cannot be in the future."))

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

    @api.depends("x_anrede", "title_id", "name", "x_anrede_calc_refresh")
    def _compute_x_anrede_calc(self):
        for partner in self:
            first_name = (partner.name or "").split()[0] if partner.name else ""
            guessed_anrede = (
                _GENDER_GUESS_TO_ANREDE.get(_GENDER_DETECTOR.get_gender(_strip_diacritics(first_name)))
                if first_name
                else None
            )
            partner.x_anrede_calc = (
                partner.x_anrede
                or _TITLE_NAME_TO_ANREDE.get(partner.title_id.name)
                or guessed_anrede
                or _DESKLINE_SALUTATION_DAMEN_UND_HERREN
            )

    @api.depends("birthdate_date", "x_manual_age", "x_underage_manual")
    def _compute_x_age(self):
        for partner in self:
            has_age = bool(partner.x_manual_age or partner.birthdate_date)
            if partner.x_manual_age:
                partner.x_age = partner.x_manual_age
            elif partner.birthdate_date:
                today = date.today()
                partner.x_age = (
                    today.year
                    - partner.birthdate_date.year
                    - ((today.month, today.day) < (partner.birthdate_date.month, partner.birthdate_date.day))
                )
            else:
                partner.x_age = 0
            partner.x_underage = partner.x_age < 16 if has_age else partner.x_underage_manual
            partner.x_taxable = not partner.x_underage

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
