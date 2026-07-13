from odoo import api, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.model
    @api.readonly
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        if not self.env.context.get("cash_journal_frontend_select"):
            return super().name_search(name=name, domain=domain, operator=operator, limit=limit)

        allowed_company_ids = self.env.context.get("allowed_company_ids") or self.env.user.company_ids.ids
        journal_domain = [
            ("type", "=", "cash"),
            "|",
            ("company_id", "=", False),
            ("company_id", "in", allowed_company_ids),
        ]
        return super(AccountJournal, self.sudo()).name_search(
            name=name,
            domain=journal_domain,
            operator=operator,
            limit=limit,
        )
