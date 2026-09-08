{
    "name": "Invoice From Mail",
    "summary": "Search Gmail for a matching invoice PDF and attach it to a bank transaction.",
    "version": "19.0.1.0.0",
    "category": "Accounting/Accounting",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        "account_accountant",
    ],
    "data": [
        "data/ir_config_parameter_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "invoice_from_mail/static/src/components/bank_reconciliation/button_list_patch.js",
            "invoice_from_mail/static/src/components/bank_reconciliation/button_list_patch.xml",
        ],
    },
    "installable": True,
    "application": False,
}
