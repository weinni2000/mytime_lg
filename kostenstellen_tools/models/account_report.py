# Copyright 2026 mytime.click
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import ast

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.account_reports.models.account_report import UNDISTR_LINE_NAME


class AccountReportExpression(models.Model):
    _inherit = "account.report.expression"

    hide_temporary = fields.Boolean(
        string="Hide Temporarily",
        help="Ignore this expression during report computation without deleting it.",
    )

    def _expand_aggregations(self):
        return super()._expand_aggregations().filtered(lambda expression: not expression.hide_temporary)


class AccountReport(models.Model):
    _inherit = "account.report"

    def _compute_expression_totals_for_each_column_group(self, expressions, options, *args, **kwargs):
        expressions = expressions.filtered(lambda expression: not expression.hide_temporary)
        return super()._compute_expression_totals_for_each_column_group(expressions, options, *args, **kwargs)

    hide_analytic_groupby_total = fields.Boolean(
        string="Hide Total column in Analytic Group By",
        help="When the Analytic Group By filter is used, don't append the extra combined "
        "'Total' column after the per-account/plan columns.",
    )

    hide_analytic_groupby_date = fields.Boolean(
        string="Hide Date column per Analytic Group",
        help="When the Analytic Group By filter is used, only show the Date column once, "
        "under the combined 'Total' group, instead of duplicating it for every "
        "account/plan group. Assumes a single top-level column header (no horizontal "
        "groups, no period comparison), since the colspan fix-up doesn't account for those.",
    )

    hide_analytic_groupby_monetary_on_total = fields.Boolean(
        string="Hide Debit/Credit on the Total column of Analytic Group By",
        help="When the Analytic Group By filter is used, don't repeat the Debit/Credit "
        "columns on the combined 'Total' group; only the columns kept there (e.g. Date) "
        "are shown. Same colspan caveats as hide_analytic_groupby_date.",
    )

    def _get_analytic_groupby_column_ids(self):
        """Report columns to keep for the per-account/plan analytic groups, and for the
        combined 'Total' group, once hide_analytic_groupby_date/_monetary_on_total apply."""
        self.ensure_one()
        per_account_columns = self.column_ids
        total_columns = self.column_ids
        if self.hide_analytic_groupby_date:
            per_account_columns = per_account_columns.filtered(lambda column: column.expression_label != "date")
        if self.hide_analytic_groupby_monetary_on_total:
            total_columns = total_columns.filtered(lambda column: column.expression_label == "date")
        return per_account_columns, total_columns

    def _create_column_analytic(self, options):
        headers_before = len(options.get("column_headers", []))
        result = super()._create_column_analytic(options)
        if len(options.get("column_headers", [])) > headers_before:
            analytic_level = options["column_headers"][-1]
            if self.hide_analytic_groupby_total:
                # The analytic groupby appended a new header level ending with the auto "Total" entry; drop it.
                analytic_level[:] = analytic_level[:-1]
            if self.hide_analytic_groupby_date or self.hide_analytic_groupby_monetary_on_total:
                # Odoo always duplicates every report column per analytic group. Give the
                # per-account/plan groups and the "Total" group (the one without
                # 'analytic_groupby_option') each a colspan matching the columns they'll
                # actually keep, and propagate the real total colspan upwards so the outer
                # header row(s) still span the correct number of columns instead of the
                # (wrong) uniform default.
                per_account_columns, total_columns = self._get_analytic_groupby_column_ids()
                for header in analytic_level:
                    is_per_account_group = header.get("forced_options", {}).get("analytic_groupby_option")
                    header["colspan"] = len(per_account_columns) if is_per_account_group else len(total_columns)
                total_colspan = sum(header["colspan"] for header in analytic_level)
                for header_level in options["column_headers"][:-1]:
                    for header in header_level:
                        header["colspan"] = total_colspan
        return result

    def _build_columns_from_column_group_vals(self, options, all_column_group_vals_in_order):
        columns, column_groups = super()._build_columns_from_column_group_vals(
            options, all_column_group_vals_in_order
        )
        has_analytic_breakdown = any(
            column_group.get("forced_options", {}).get("analytic_groupby_option")
            for column_group in column_groups.values()
        )
        if has_analytic_breakdown and (
            self.hide_analytic_groupby_date or self.hide_analytic_groupby_monetary_on_total
        ):
            per_account_columns, total_columns = self._get_analytic_groupby_column_ids()
            per_account_labels = set(per_account_columns.mapped("expression_label"))
            total_labels = set(total_columns.mapped("expression_label"))

            def _column_is_kept(column):
                is_per_account_group = (
                    column_groups.get(column["column_group_key"], {})
                    .get("forced_options", {})
                    .get("analytic_groupby_option")
                )
                allowed_labels = per_account_labels if is_per_account_group else total_labels
                return column["expression_label"] in allowed_labels

            columns = [column for column in columns if _column_is_kept(column)]
        return columns, column_groups

    def caret_option_open_general_ledger_privat(self, options, params):
        # Same as caret_option_open_general_ledger, but redirects to the "Privat" General
        # Ledger report instead of the standard one, so drill-downs from Privataufteilung
        # lines stay scoped to the private-category entries.
        options["unfold_all"] = True
        general_ledger = self.env.ref("kostenstellen_tools.privat_general_ledger_report")
        account_id_to_search = self._get_res_id_from_line_id(params["line_id"], "account.account")
        company_id_to_search = self._get_res_id_from_line_id(params["line_id"], "res.company")
        if not account_id_to_search and not company_id_to_search:
            raise UserError(
                _(
                    "'Open General Ledger' caret option is only available form report lines "
                    "targetting accounts or Result Brought Forward."
                )
            )

        if account_id_to_search:
            search_content = self.env["account.account"].browse(account_id_to_search).code
        elif len(self.env.companies) == 1:
            search_content = str(UNDISTR_LINE_NAME)
        else:
            search_content = _(
                "%(line_name)s - %(company_name)s",
                line_name=UNDISTR_LINE_NAME,
                company_name=self.env["res.company"].browse(company_id_to_search).name,
            )
        gl_options = general_ledger.get_options(options)
        gl_options["not_reset_journals_filter"] = True
        gl_options["unfold_all"] = True
        gl_options["filter_search_bar"] = search_content

        action_vals = self.env["ir.actions.actions"]._for_xml_id(
            "kostenstellen_tools.action_account_report_privat_general_ledger"
        )
        action_vals["params"] = {
            "options": gl_options,
            "ignore_session": True,
        }
        action_vals["context"] = dict(
            ast.literal_eval(action_vals["context"]), default_filter_accounts=search_content
        )

        return action_vals
