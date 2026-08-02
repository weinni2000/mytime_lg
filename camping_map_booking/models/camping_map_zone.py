from odoo import api, fields, models


class CampingMapZone(models.Model):
    _name = "camping.map.zone"
    _description = "Camping Map Zone"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    points = fields.Char(
        required=True,
        help=(
            "Polygon outline of this zone on the campsite map, as SVG points"
            ' in the source image\'s own pixel space: "x1,y1 x2,y2 x3,y3 ...".'
        ),
    )
    product_template_ids = fields.One2many("product.template", "camping_map_zone_id", string="Pitches")
    product_count = fields.Integer(compute="_compute_product_count")

    @api.depends("product_template_ids")
    def _compute_product_count(self):
        for record in self:
            record.product_count = len(record.product_template_ids)

    def action_view_map(self):
        return {
            "type": "ir.actions.client",
            "tag": "camping_map_booking.map_preview_action",
            "name": self.env._("Camping Map"),
        }
