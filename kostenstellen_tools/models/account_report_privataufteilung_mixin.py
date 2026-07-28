# Copyright 2026 mytime.click
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models

PRIVATAUFTEILUNG_PLAN_NAME = "Privataufteilung"


class AccountReportPrivataufteilungMixin(models.AbstractModel):
    _name = "account.report.privataufteilung.mixin"
    _description = "Privataufteilung Analytic Plan Helper"

    def _get_privataufteilung_analytic_account_ids(self):
        plan = self.env["account.analytic.plan"].search([("name", "=", PRIVATAUFTEILUNG_PLAN_NAME)], limit=1)
        if not plan:
            return []
        return self.env["account.analytic.account"].search([("plan_id", "=", plan.id)]).ids
