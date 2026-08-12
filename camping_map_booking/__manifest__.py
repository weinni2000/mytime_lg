{
    "name": "Camping Map Booking",
    "summary": "Interactive campsite map with clickable areas linking to rentable pitches.",
    "version": "19.0.1.1.3",
    "category": "Sales/Rental",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        # "campsite", # manually check if it's installed
        "planning",
        "product",
        "ressource_map",
        "website_sale_renting",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/camping_map_zone_views.xml",
        "views/camping_map_state_views.xml",
        "views/camping_vehicle_type_views.xml",
        "views/planning_role_views.xml",
        "views/campsite_map_views.xml",
        "data/camping_vehicle_type_data.xml",
        "data/camping_map_state_data.xml",
    ],
    "demo": [
        "demo/camping_map_zone_demo.xml",
        "demo/planning_role_demo.xml",
        "demo/product_template_demo.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "camping_map_booking/static/src/interactions/**/*",
            "camping_map_booking/static/src/scss/*.scss",
        ],
        "web.assets_backend": [
            "camping_map_booking/static/src/backend/**/*",
            "camping_map_booking/static/src/scss/*.scss",
        ],
    },
    "installable": True,
    "application": False,
    "pre_init_hook": "pre_init_hook",
}
