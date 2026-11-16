{
    "name": "Industry Adaption",
    "summary": "Local adaptions to the Odoo industry modules.",
    "version": "19.0.1.0.1",
    "category": "Sales/Rental",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        "booking_engine",
        "industry_real_estate",
    ],
    "data": [
        "views/rental_order_wizard_views.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "installable": True,
    "application": False,
}
