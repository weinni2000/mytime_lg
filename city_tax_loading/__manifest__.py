{
    "name": "City Tax - Loading",
    "summary": "Load guest tax messages from a Google Sheet or uploaded file for a selected month.",
    "version": "19.0.1.0.5",
    "category": "Hidden/Tools",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": ["city_tax"],
    "external_dependencies": {"python": ["requests", "openpyxl"]},
    "data": [
        "security/ir.model.access.csv",
        "views/guest_tax_sheet_views.xml",
    ],
    "installable": True,
    "application": False,
}
