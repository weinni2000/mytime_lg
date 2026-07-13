from odoo import api, fields, models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    receipt_image = fields.Binary(
        string="Receipt Image",
        related="message_main_attachment_id.datas",
    )

    def _sanitize_cash_analytic_distribution(self, analytic_distribution, company_id):
        if not isinstance(analytic_distribution, dict):
            return {}

        distribution_values = []
        analytic_account_ids = []
        for key, value in analytic_distribution.items():
            try:
                analytic_account_id = int(key)
            except (TypeError, ValueError):
                continue
            distribution_values.append((str(analytic_account_id), value))
            analytic_account_ids.append(analytic_account_id)

        if not analytic_account_ids:
            return {}

        analytic_account_model = self.env["account.analytic.account"].sudo()
        analytic_account_by_id = {
            analytic_account.id: analytic_account
            for analytic_account in analytic_account_model.browse(analytic_account_ids).exists()
        }

        sanitized_distribution = {}
        for analytic_account_key, value in distribution_values:
            analytic_account = analytic_account_by_id.get(int(analytic_account_key))
            if not analytic_account:
                continue
            if analytic_account.company_id and analytic_account.company_id != company_id:
                continue
            sanitized_distribution[analytic_account_key] = value

        return sanitized_distribution

    @api.model_create_multi
    def create(self, vals_list):
        analytic_distributions = [vals.pop("cash_analytic_distribution", None) for vals in vals_list]
        analytic_tag_ids_by_line = [vals.pop("cash_analytic_tag_ids", []) for vals in vals_list]
        statement_line_ids = super().create(vals_list)
        for statement_line_id, analytic_distribution, analytic_tag_ids in zip(
            statement_line_ids, analytic_distributions, analytic_tag_ids_by_line, strict=True
        ):
            default_account_id = statement_line_id.journal_id.default_account_id
            for line_id in statement_line_id.line_ids:
                if line_id.account_id != default_account_id:
                    line_values = {}
                    if analytic_distribution:
                        sanitized_distribution = self._sanitize_cash_analytic_distribution(
                            analytic_distribution, statement_line_id.company_id
                        )
                        if sanitized_distribution:
                            line_values["analytic_distribution"] = sanitized_distribution
                    if analytic_tag_ids and "analytic_tag_ids" in line_id._fields:
                        line_values["analytic_tag_ids"] = [(6, 0, analytic_tag_ids)]
                    if line_values:
                        line_id.write(line_values)
        return statement_line_ids
