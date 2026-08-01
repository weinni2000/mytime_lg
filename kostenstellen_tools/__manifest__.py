# Copyright 2026 mytime.click
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Kostenstellen Tools",
    "summary": "Additional tools for journal items",
    "version": "19.0.1.0.0",
    "category": "Accounting/Accounting",
    "license": "AGPL-3",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        "account",
        "account_reports",
        "analytic",
        "knowledge",
        "l10n_at",
    ],
    "data": [
        "data/account_report_privat.xml",
        "data/account_report_privataufteilung.xml",
        "views/account_move_line_views.xml",
        "views/account_report_expression_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            (
                "after",
                "knowledge/static/src/components/knowledge_dropdown/knowledge_dropdown_patch.js",
                "kostenstellen_tools/static/src/js/knowledge_dropdown_patch.js",
            ),
        ],
    },
    "installable": True,
    "application": False,
}
