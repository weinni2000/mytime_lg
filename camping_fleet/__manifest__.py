{
    "name": "Camping Fleet",
    "summary": "Assign camping vehicles to sales orders.",
    "version": "19.0.1.0.0",
    "category": "Sales/Sales",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": ["fleet", "sale"],
    "data": [
        "security/ir.model.access.csv",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
