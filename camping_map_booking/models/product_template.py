from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    camping_map_zone_id = fields.Many2one("camping.map.zone", string="Camping Map Zone")
