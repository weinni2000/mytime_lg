{
    "name": "Camping Automation",
    "summary": "Import Guesty reservations as confirmed rental bookings twice a day.",
    "version": "19.0.1.0.0",
    "category": "Sales/Rental",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
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
    ],
    "installable": True,
    "application": False,
}
