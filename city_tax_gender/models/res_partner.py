from odoo import api, models

from odoo.addons.city_tax.models._const import _DESKLINE_SALUTATION_FRAU, _DESKLINE_SALUTATION_HERR
from odoo.addons.city_tax.models.res_partner import _TITLE_NAME_TO_ANREDE

_CALCULATED_GENDER_TO_ANREDE = {
    "male": _DESKLINE_SALUTATION_HERR,
    "female": _DESKLINE_SALUTATION_FRAU,
}


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.depends("properties")
    def _compute_x_anrede_calc(self):
        super()._compute_x_anrede_calc()
        for partner in self:
            if partner.x_anrede or _TITLE_NAME_TO_ANREDE.get(partner.title_id.name):
                continue
            gender = partner.with_context(property_selection_get_key=True).properties.get("calculated_gender")
            anrede = _CALCULATED_GENDER_TO_ANREDE.get(gender)
            if anrede:
                partner.x_anrede_calc = anrede
        return None
