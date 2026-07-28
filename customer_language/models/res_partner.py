# Copyright 2026 mytime.click
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    communication_lang_id = fields.Many2one(
        "res.lang",
        string="Customer Language",
        domain=[],
        context={"active_test": False},
        help=("Language used for external translation (DeepSeek), independent " "from installed UI languages."),
    )

    def _get_communication_language_from_country(self, country):
        if not country:
            return self.env["res.lang"]

        languages = self.env["res.lang"].with_context(active_test=False).search([])
        if country.lang:
            configured_language = languages.filtered(lambda language: language.code == country.lang)
            if configured_language:
                return configured_language[:1]

        country_code = country.code.upper()
        country_languages = languages.filtered(
            lambda language: language.code.replace("-", "_").split("_")[-1].upper() == country_code
        )
        preferred_language = country_languages.filtered(
            lambda language: language.code.split("_")[0].lower() == country_code.lower()
        )
        return (preferred_language or country_languages).sorted("code")[:1]

    @api.onchange("country_id")
    def _onchange_country_id_set_communication_language(self):
        for partner in self:
            if not partner.communication_lang_id:
                partner.communication_lang_id = partner._get_communication_language_from_country(
                    partner.country_id
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("country_id") and not vals.get("communication_lang_id"):
                country = self.env["res.country"].browse(vals["country_id"])
                vals["communication_lang_id"] = self._get_communication_language_from_country(country).id
        return super().create(vals_list)

    def write(self, vals):
        result = super().write(vals)
        if "country_id" in vals and "communication_lang_id" not in vals:
            for partner in self.filtered(lambda item: not item.communication_lang_id):
                partner.communication_lang_id = partner._get_communication_language_from_country(
                    partner.country_id
                )
        return result
