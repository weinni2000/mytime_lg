{
    "name": "Flower Calculator",
    "summary": "Count flowers from a photo with ChatGPT and add them to the sale order.",
    "version": "19.0.1.0.0",
    "category": "Sales/Sales",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "price": 0.0,
    "depends": ["sale", "ai"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_company_views.xml",
        "views/res_config_settings_views.xml",
        "views/flower_calculator_mapping_views.xml",
        "views/flower_calculator_flower_views.xml",
        "wizard/flower_calculator_mapping_wizard_views.xml",
        "views/sale_order_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "assets": {
        "web.assets_backend": [
            "flower_calculator/static/src/fields/image_fullscreen/image_fullscreen.js",
            "flower_calculator/static/src/fields/image_fullscreen/image_fullscreen.xml",
        ],
    },
    "installable": True,
    "application": False,
}
