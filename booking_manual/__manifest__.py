{
    "name": "Booking Manual",
    "summary": "Log in to Booking.com with Playwright and forwarded SMS codes.",
    "version": "19.0.1.10.9",
    "category": "Sales/Rental",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/booking_account_views.xml",
    ],
    "external_dependencies": {"python": ["playwright", "psycopg2"]},
    "installable": True,
    "application": False,
}
