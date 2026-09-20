{
    "name": "Insert From Mail",
    "summary": "Create camping rental bookings from booking platform emails.",
    "version": "19.0.1.0.1",
    "category": "Sales/Rental",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        "sale_renting",
        "sale_channel",
        "booking_engine",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/insert_from_mail_data.xml",
        "views/insert_from_mail_views.xml",
    ],
    "installable": True,
    "application": False,
}
