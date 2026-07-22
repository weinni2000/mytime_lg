{
    "name": "Mail Global Inbox",
    "summary": "Global view of all incoming emails across all models",
    "version": "19.0.1.0",
    "website": "https://github.com/OCA/odoo-pim",
    "category": "Discuss",
    "author": "IT Fact",
    "depends": ["mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/mail_message_views.xml",
        "views/mail_message_menu.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
