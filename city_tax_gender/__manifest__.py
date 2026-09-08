{
    "name": "City Tax Gender",
    "summary": "AI-calculated guest gender, stored as a Property on contacts.",
    "version": "19.0.1.0.0",
    "category": "Hidden/Tools",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        "city_tax",
        "ai_fields",
    ],
    "data": [
        "views/res_partner_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
}
