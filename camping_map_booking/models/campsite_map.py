from odoo import api, fields, models


class CampsiteMap(models.Model):
    _name = "campsite.map"
    _description = "Campsite Map"
    _order = "name, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    image = fields.Binary(required=True, attachment=True)
    zone_ids = fields.One2many("camping.map.zone", "map_id", string="Zones")
    preview_data = fields.Json(compute="_compute_preview_data")

    @api.depends(
        "image",
        "zone_ids.name",
        "zone_ids.code",
        "zone_ids.symbol",
        "zone_ids.points",
        "zone_ids.availability_state",
    )
    def _compute_preview_data(self):
        for record in self:
            map_id = record.id if isinstance(record.id, int) else False
            available_zones = self.env["camping.map.zone"].search([])
            image_url = (
                f"/web/image/campsite.map/{record.id}/image"
                if record.id and record.image
                else "/camping_map_booking/static/src/img/camping_map.png"
            )
            shapes = []
            for zone in available_zones:
                shapes += zone._get_map_shapes(zone.availability_state)
            record.preview_data = {
                "map_id": map_id,
                "image_url": image_url,
                "zones": [
                    {
                        "id": zone.id,
                        "name": zone.name,
                        "code": zone.code,
                        "symbol": zone.symbol,
                        "map_id": zone.map_id.id,
                    }
                    for zone in available_zones
                ],
                "shapes": shapes,
            }
