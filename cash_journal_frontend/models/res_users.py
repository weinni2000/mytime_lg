from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    cash_company_id = fields.Many2one(
        comodel_name="res.company",
        string="Cash Company",
        domain="[('id', 'in', allowed_company_ids)]",
        help="Default company used by the /cash frontend transaction page.",
    )
    cash_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Cash Journal",
        domain=(
            "[('type', '=', 'cash'), '|', "
            "('company_id', '=', False), "
            "('company_id', 'in', allowed_company_ids)]"
        ),
        check_company=True,
        help="Default cash journal used by the /cash frontend transaction page.",
    )
    cash_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cash Account",
        domain="[('company_ids', 'parent_of', allowed_company_ids)]",
        help="Default counterpart account used by the /cash frontend transaction page.",
    )
    cash_analytic_plan_id = fields.Many2one(
        comodel_name="account.analytic.plan",
        string="Cash Analytic Plan",
        help="Analytic plan used to select the default analytic account below.",
    )
    cash_analytic_account_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Cash Analytic Account",
        domain=(
            "[('plan_id', '=', cash_analytic_plan_id), '|', "
            "('company_id', '=', False), "
            "('company_id', 'in', allowed_company_ids)]"
        ),
        check_company=True,
        help="Default analytic account used by the /cash frontend transaction page.",
    )
    cash_analytic_tag_ids = fields.Many2many(
        comodel_name="account.analytic.tag",
        string="Cash Analytic Tags",
        help="Default analytic tags always applied to /cash frontend move lines.",
    )
    cash_manual_distribution_id = fields.Many2one(
        comodel_name="account.analytic.distribution.manual",
        string="Cash Manual Distribution",
        domain=("['|', ('company_id', '=', False), " "('company_id', 'in', allowed_company_ids)]"),
        help=("Default manual analytic distribution used to prefill the /cash " "frontend transaction page."),
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + [
            "cash_company_id",
            "cash_journal_id",
            "cash_account_id",
            "cash_analytic_plan_id",
            "cash_analytic_account_id",
            "cash_analytic_tag_ids",
            "cash_manual_distribution_id",
        ]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + [
            "cash_company_id",
            "cash_journal_id",
            "cash_account_id",
            "cash_analytic_plan_id",
            "cash_analytic_account_id",
            "cash_analytic_tag_ids",
            "cash_manual_distribution_id",
        ]
