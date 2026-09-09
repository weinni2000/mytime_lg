{
    "name": "Camping Automation",
    "summary": "Import Guesty reservations as confirmed rental bookings twice a day.",
    "version": "19.0.1.0.1",
    "category": "Sales/Rental",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        "booking_engine",
        "camping_base",
        "camping_checkout",
        "sale",
        "sale_renting",
        "sale_planning",
        "sale_channel",
        "planning",
    ],
    "external_dependencies": {
        "python": ["requests"],
    },
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
