import json

from odoo import fields, http
from odoo.http import request


class CampingMapBookingController(http.Controller):
    @http.route("/camping/map", type="http", auth="public", website=True, sitemap=True)
    def camping_map(self, vehicle_type_id=None, **kwargs):
        zones = (
            request.env["camping.map.zone"]
            .sudo()
            .search(
                [
                    ("points", "!=", False),
                    ("hide_on_frontend_map", "=", False),
                ]
            )
        )
        vehicle_type = None
        if vehicle_type_id and vehicle_type_id.isdigit():
            vehicle_type = request.env["camping.vehicle.type"].sudo().browse(int(vehicle_type_id))
            if not vehicle_type.exists():
                vehicle_type = None
        now = fields.Datetime.now()
        shapes = []
        for zone in zones:
            state = zone._get_availability_state(vehicle_type, now)
            shapes += zone._get_map_shapes(state)
        values = {
            "zones_json": json.dumps(shapes),
            "map_image_url": "/camping_map_booking/static/src/img/camping_map.png",
            "vehicle_types": request.env["camping.vehicle.type"].sudo().search([]),
            "selected_vehicle_type_id": vehicle_type.id if vehicle_type else False,
        }
        return request.render("camping_map_booking.map_page", values)
