{
    "name": "Camping Base",
    "summary": "Shared configuration and navigation for camping modules.",
    "version": "19.0.1.0.0",
    "category": "Sales/Rental",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": ["base", "booking_engine"],
    "post_init_hook": "post_init_hook",
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_tag_data.xml",
        "views/ir_cron_views.xml",
    ],
    "installable": True,
    "application": False,
}
