import json

from odoo import http
from odoo.http import request


class CampingMapBookingController(http.Controller):
    @http.route("/camping/map", type="http", auth="public", website=True, sitemap=True)
    def camping_map(self, **kwargs):
        zones = request.env["camping.map.zone"].sudo().search([])
        zones_data = [
            {
                "id": zone.id,
                "name": zone.name,
                "points": zone.points,
                "products": [
                    {
                        "id": product.id,
                        "name": product.name,
                        "price": product.list_price,
                        "url": product.website_url,
                    }
                    for product in zone.product_template_ids.filtered("website_published")
                ],
            }
            for zone in zones
        ]
        values = {
            "zones_json": json.dumps(zones_data),
            "map_image_url": "/camping_map_booking/static/src/img/camping_map.png",
        }
        return request.render("camping_map_booking.map_page", values)
