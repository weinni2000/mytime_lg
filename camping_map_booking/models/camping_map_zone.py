from odoo import api, fields, models

from .camping_map_state import STATE_FREE, STATE_NOT_SUITABLE, STATE_OCCUPIED


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
    hide_on_frontend_map = fields.Boolean(
        string="Hide on Frontend Map",
        help="Hide this zone on the public website map.",
    )
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

    @api.depends("pitch_source", "product_template_ids", "resource_ids")
    def _compute_product_count(self):
        for record in self:
            record.product_count = len(
                record.product_template_ids if record.pitch_source == "product" else record.resource_ids
            )

    def _get_availability_state(self, vehicle_type=None, start=None, end=None):
        self.ensure_one()
        if not self.resource_ids:
            return False
        start = start or fields.Datetime.now()
        states = {self._get_resource_state(resource, vehicle_type, start, end) for resource in self.resource_ids}
        if STATE_FREE in states:
            return STATE_FREE
        return STATE_OCCUPIED if STATE_OCCUPIED in states else STATE_NOT_SUITABLE

    def _get_resource_state(self, resource, vehicle_type, start, end=None):
        if vehicle_type and not self._is_vehicle_allowed(resource, vehicle_type):
            return STATE_NOT_SUITABLE
        return STATE_FREE if self.is_resource_free(resource, start, end) else STATE_OCCUPIED

    def _is_vehicle_allowed(self, resource, vehicle_type):
        # Vehicle suitability comes from the resource's planning role(s)
        # (allowed_vehicle_type_ids). An empty list means "allow any"; a
        # non-empty list must contain the checked vehicle.
        role_allowed = resource.role_ids.allowed_vehicle_type_ids
        return not role_allowed or vehicle_type in role_allowed

    def is_resource_free(self, resource, start, end=None):
        # Range check when an end is given (stay across nights), otherwise a
        # single-instant check. Two intervals overlap iff each starts before the
        # other ends: slot.start < end and slot.end > start.
        if end and end > start:
            overlap = [("start_datetime", "<", end), ("end_datetime", ">", start)]
        else:
            overlap = [("start_datetime", "<=", start), ("end_datetime", ">", start)]
        return not self.env["planning.slot"].search_count([("resource_id", "=", resource.id), *overlap])

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
                # Colors resolved from the camping.map.state model so the map
                # renders straight from that single source of truth.
                "colors": self.env["camping.map.state"]._colors_for(state),
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
