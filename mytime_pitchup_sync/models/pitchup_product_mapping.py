from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PitchupProductMapping(models.Model):
    _name = "pitchup.product.mapping"
    _description = "Pitchup Pitch Type Product Mapping"
    _order = "pitch_type_id"

    pitch_type_id = fields.Integer(string="Pitchup Pitch Type ID", required=True)
    pitch_type_name = fields.Char(string="Pitchup Pitch Type")
    product_template_id = fields.Many2one(
        "product.template",
        string="Stay Offer",
        required=True,
        domain="[('x_is_a_room_offer', '=', True)]",
        ondelete="restrict",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )

    _pitch_type_company_unique = models.Constraint(
        "UNIQUE(pitch_type_id, company_id)",
        "A product mapping already exists for this Pitchup pitch type and company.",
    )

    @api.constrains("product_template_id")
    def _check_product_template_id_is_room_offer(self):
        for mapping_id in self:
            if not mapping_id.product_template_id.x_is_a_room_offer:
                raise ValidationError(
                    _(
                        "Pitchup pitch types can only be mapped to stay offers from "
                        "Booking > Configuration > Stay Offers > Offers."
                    )
                )

    def action_sync_pitchup_product_mappings(self):
        return self.env.company.sudo().action_sync_pitchup_product_mappings()
