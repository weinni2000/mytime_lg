{
    "name": "Camping Map Booking",
    "summary": "Interactive campsite map with clickable areas linking to rentable pitches.",
    "version": "19.0.1.0.0",
    "category": "Sales/Rental",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        "product",
        "website_sale_renting",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/camping_map_zone_views.xml",
        "views/product_template_views.xml",
        "views/camping_map_booking_templates.xml",
        "data/website_menu.xml",
    ],
    "demo": [
        "demo/camping_map_zone_demo.xml",
        "demo/product_template_demo.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "camping_map_booking/static/src/interactions/**/*",
            "camping_map_booking/static/src/components/**/*",
            "camping_map_booking/static/src/scss/*.scss",
        ],
        "web.assets_backend": [
            "camping_map_booking/static/src/backend/**/*",
            "camping_map_booking/static/src/components/**/*",
            "camping_map_booking/static/src/scss/*.scss",
        ],
    },
    "installable": True,
    "application": False,
}
