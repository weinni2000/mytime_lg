# Copyright 2026 mytime.click
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class AccountGeneralLedgerPrivatReportHandler(models.AbstractModel):
    _name = "account.general.ledger.privat.report.handler"
    _inherit = [
        "account.general.ledger.report.handler",
        "account.report.privataufteilung.mixin",
    ]
    _description = "General Ledger (Privat) Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        analytic_account_ids = self._get_privataufteilung_analytic_account_ids()
        if analytic_account_ids:
            options["forced_domain"] = options.get("forced_domain", []) + [
                ("analytic_distribution", "in", analytic_account_ids),
            ]
