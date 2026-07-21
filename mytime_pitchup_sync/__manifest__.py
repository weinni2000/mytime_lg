{
    "name": "Mytime Pitchup Sync",
    "summary": "Synchronize Pitchup bookings with Odoo rental orders.",
    "version": "19.0.2.0.0",
    "category": "Sales/Rental",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        "base",
        "sale_renting",
        "sale_channel",
        "sale_renting_planning",
    ],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "views/res_company_views.xml",
        "wizard/pitchup_sync_wizard_views.xml",
        "data/ir_cron.xml",
    ],
    "installable": True,
    "application": False,
}
