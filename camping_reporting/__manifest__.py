{
    "name": "Camping Reporting",
    "summary": "Daily campsite occupancy analysis by pitch and booking.",
    "version": "19.0.1.0.0",
    "category": "Sales/Rental",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        "camping_additional_fields_base",
        "city_tax",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/campsite_occupancy_report_views.xml",
    ],
    "installable": True,
    "application": False,
}
