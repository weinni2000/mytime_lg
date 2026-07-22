from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    pitchup_mapping_ids = fields.One2many(
        "pitchup.product.mapping",
        "product_template_id",
        string="Pitchup Mappings",
    )

    def action_sync_pitchup_product_mappings(self):
        return self.env.company.sudo().action_sync_pitchup_product_mappings()
