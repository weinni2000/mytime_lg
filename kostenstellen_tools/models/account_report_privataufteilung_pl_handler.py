# Copyright 2026 mytime.click
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models

from .account_move_line_privatkategorie import PRIVATKATEGORIE_GROUPBY_FIELD


class AccountReportPrivataufteilungPlHandler(models.AbstractModel):
    _name = "account.report.privataufteilung.pl.handler"
    _inherit = [
        "account.report.custom.handler",
        "account.report.privataufteilung.mixin",
    ]
    _description = "Profit and Loss (Privataufteilung) Custom Handler"

    def _caret_options_initializer(self):
        result = super()._caret_options_initializer()
        result["account.account"] = [
            {"name": _("General Ledger NW"), "action": "caret_option_open_general_ledger_privat"},
        ]
        return result

    def _custom_options_initializer(self, report, options, previous_options):
        result = super()._custom_options_initializer(report, options, previous_options=previous_options)
        analytic_account_ids = self._get_privataufteilung_analytic_account_ids()
        if analytic_account_ids:
            options["forced_domain"] = options.get("forced_domain", []) + [
                ("analytic_distribution", "in", analytic_account_ids),
            ]
        return result

    def _get_custom_groupby_map(self):
        result = super()._get_custom_groupby_map()
        result[PRIVATKATEGORIE_GROUPBY_FIELD] = {
            "model": "account.analytic.account",
            "domain_builder": lambda value: [("analytic_distribution", "in", [value])] if value else [],
        }
        return result
