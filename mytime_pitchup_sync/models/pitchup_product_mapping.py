from odoo import fields, models


class PitchupProductMapping(models.Model):
    _name = "pitchup.product.mapping"
    _description = "Pitchup Pitch Type Product Mapping"
    _order = "pitch_type_id"

    pitch_type_id = fields.Integer(string="Pitchup Pitch Type ID", required=True)
    product_id = fields.Many2one(
        "product.product",
        string="Rental Product",
        required=True,
        domain="[('rent_ok', '=', True)]",
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
