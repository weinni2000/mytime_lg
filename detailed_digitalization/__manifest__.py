{
    "name": "Detailed Digitalization",
    "summary": "Extract a full line-by-line breakdown of vendor bills using ChatGPT.",
    "version": "19.0.1.0.0",
    "category": "Accounting",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        "account_invoice_extract",
        "ai",
    ],
    "data": [
        "views/account_move_views.xml",
        "views/res_company_views.xml",
    ],
    "installable": True,
    "application": False,
}
