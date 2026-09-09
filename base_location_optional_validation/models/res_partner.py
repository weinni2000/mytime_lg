from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.constrains("zip_id", "country_id", "city_id", "state_id", "zip")
    def _check_zip(self):
        records_to_check = self.filtered(lambda record: (record.company_id or self.env.company).validate_locations)
        if not records_to_check:
            return None
        return super(ResPartner, records_to_check)._check_zip()
