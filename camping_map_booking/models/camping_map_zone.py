from odoo import api, fields, models


class CampingMapZone(models.Model):
    _name = "camping.map.zone"
    _description = "Camping Map Zone"
    _order = "sequence, id"

    name = fields.Char(required=True)
    code = fields.Char()
    symbol = fields.Selection(
        [
            ("fa-home", "Cabin"),
            ("fa-truck", "Caravan / RV"),
            ("fa-car", "Car / Parking"),
            ("fa-tree", "Wooded"),
            ("fa-tint", "Water"),
            ("fa-plug", "Electricity"),
            ("fa-toilet", "Sanitary"),
            ("fa-shower", "Shower"),
            ("fa-fire", "Fire Pit"),
            ("fa-wifi", "WiFi"),
            ("fa-paw", "Pets Allowed"),
            ("fa-map-marker", "Generic Marker"),
        ],
    )
    map_id = fields.Many2one("campsite.map", ondelete="cascade")
    pitch_source = fields.Selection(
        [("product", "Rental Products"), ("resource", "Resources")],
        required=True,
        default="product",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    points = fields.Char(
        help=(
            "Polygon outline of this zone on the campsite map, as SVG points"
            ' in the source image\'s own pixel space: "x1,y1 x2,y2 x3,y3 ...".'
        ),
    )
    product_template_ids = fields.One2many(
        "product.template",
        "camping_map_zone_id",
        string="Rental Products",
        domain=[("rent_ok", "=", True)],
    )
    resource_ids = fields.Many2many("resource.resource", string="Resources")
    product_count = fields.Integer(compute="_compute_product_count")
    availability_check_datetime = fields.Datetime(
        string="Check Availability At",
        default=fields.Datetime.now,
    )
    vehicle_type_id = fields.Many2one(
        "camping.vehicle.type",
        string="Check Vehicle",
        help="Vehicle type to check resource suitability for. Leave empty to ignore vehicle suitability.",
    )
    availability_state = fields.Selection(
        [
            ("free", "Free"),
            ("occupied", "Occupied"),
            ("not_suitable", "Not Suitable"),
        ],
        string="Availability",
        compute="_compute_availability_state",
    )

    @api.depends("pitch_source", "product_template_ids", "resource_ids")
    def _compute_product_count(self):
        for record in self:
            record.product_count = len(
                record.product_template_ids if record.pitch_source == "product" else record.resource_ids
            )

    @api.depends(
        "resource_ids",
        "resource_ids.vehicle_type_ids",
        "availability_check_datetime",
        "vehicle_type_id",
    )
    def _compute_availability_state(self):
        for zone in self:
            zone.availability_state = (
                zone._get_availability_state(zone.vehicle_type_id, zone.availability_check_datetime)
                if zone.availability_check_datetime
                else False
            )

    def _get_availability_state(self, vehicle_type=None, at=None):
        self.ensure_one()
        if not self.resource_ids:
            return False
        at = at or fields.Datetime.now()
        states = {self._get_resource_state(resource, vehicle_type, at) for resource in self.resource_ids}
        if "free" in states:
            return "free"
        return "occupied" if "occupied" in states else "not_suitable"

    def _get_resource_state(self, resource, vehicle_type, at):
        if vehicle_type and resource.vehicle_type_ids and vehicle_type not in resource.vehicle_type_ids:
            return "not_suitable"
        return "free" if self.is_resource_free(resource, at) else "occupied"

    def is_resource_free(self, resource, at):
        return not self.env["planning.slot"].search_count(
            [
                ("resource_id", "=", resource.id),
                ("start_datetime", "<=", at),
                ("end_datetime", ">", at),
            ]
        )

    def _get_map_shapes(self, state=False):
        self.ensure_one()
        products = self._get_map_items()
        if not self.points:
            return []
        return [
            {
                "id": f"zone-{self.id}",
                "zone_id": self.id,
                "name": self.name,
                "code": self.code,
                "symbol": self.symbol,
                "points": self.points,
                "products": products,
                "state": state,
            }
        ]

    def _get_map_items(self):
        self.ensure_one()
        if self.pitch_source == "resource":
            return [
                {"id": resource.id, "name": resource.name, "price": "", "url": False}
                for resource in self.resource_ids
            ]
        return [
            {
                "id": product.id,
                "name": product.name,
                "price": product.list_price,
                "url": product.website_url,
            }
            for product in self.product_template_ids.filtered("website_published")
        ]

    def action_view_map(self):
        return {
            "type": "ir.actions.client",
            "tag": "camping_map_booking.map_preview_action",
            "name": self.env._("Camping Map"),
        }

    def action_open_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "camping.map.zone",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }
