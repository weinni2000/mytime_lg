from odoo import Command, _
from odoo.exceptions import UserError


def post_init_hook(env):
    journal_id = (
        env["account.journal"]
        .sudo()
        .with_context(active_test=False)
        .search(
            [
                ("name", "=", "Bargeld NW"),
                ("type", "=", "cash"),
            ],
            limit=1,
        )
    )
    if not journal_id:
        raise UserError(_("Cash journal 'Bargeld NW' was not found."))

    account_domain = [("code", "=", "9400")]
    account_model = env["account.account"].sudo()
    if journal_id.company_id:
        account_domain.append(("company_ids", "in", journal_id.company_id.ids))
        account_model = account_model.with_company(journal_id.company_id)
    account_id = account_model.search(account_domain, limit=1)
    if not account_id:
        raise UserError(_("Account '9400' was not found."))

    analytic_plan_id = (
        env["account.analytic.plan"]
        .sudo()
        .search(
            [("name", "=", "Privatkategorie")],
            limit=1,
        )
    )
    if not analytic_plan_id:
        raise UserError(_("Analytic plan 'Privatkategorie' was not found."))

    user_ids = env["res.users"].sudo().with_context(active_test=False).search([])
    if journal_id.company_id:
        user_ids.filtered(lambda user_id: journal_id.company_id not in user_id.company_ids).write(
            {"company_ids": [Command.link(journal_id.company_id.id)]}
        )
    user_ids.write(
        {
            "cash_journal_id": journal_id.id,
            "cash_account_id": account_id.id,
            "cash_analytic_plan_id": analytic_plan_id.id,
        }
    )
