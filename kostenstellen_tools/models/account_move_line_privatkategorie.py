# Copyright 2026 mytime.click
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.tools import SQL

PRIVATKATEGORIE_PLAN_NAME = "Privatkategorie"
PRIVATKATEGORIE_GROUPBY_FIELD = "privatkategorie_analytic_account_id"


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _field_to_sql(self, alias, fname, query=None):
        if fname == PRIVATKATEGORIE_GROUPBY_FIELD:
            plan = self.env["account.analytic.plan"].search([("name", "=", PRIVATKATEGORIE_PLAN_NAME)], limit=1)
            if not plan:
                return SQL("NULL")

            distribution_sql = super()._field_to_sql(alias, "analytic_distribution", query)
            # analytic_distribution normally maps comma-separated analytic account ids to a
            # percentage (a JSON object). But when the report's "Analytic Group By" filter is
            # active, account_move_line is shadowed by account_analytic_line rows, where it is a
            # plain JSON scalar holding a single analytic account id instead. Branch on the actual
            # runtime JSON type rather than on context, since the context flag used to decide the
            # shadowing isn't visible by the time this groupby SQL gets built.
            # Lines split across several categories of this plan aren't proportionally divided:
            # the one with the dominant share "wins" for grouping purposes.
            return SQL(
                """(
                    CASE jsonb_typeof(%(distribution)s)
                        WHEN 'object' THEN (
                            SELECT account.id
                            FROM jsonb_each_text(%(distribution)s) AS distribution(key, value)
                            JOIN LATERAL regexp_split_to_table(
                                distribution.key, ','
                            ) AS split(account_id_text) ON TRUE
                            JOIN account_analytic_account account ON account.id = split.account_id_text::int
                            WHERE account.plan_id = %(plan_id)s
                            ORDER BY distribution.value::float DESC
                            LIMIT 1
                        )
                        WHEN 'number' THEN (
                            SELECT account.id
                            FROM account_analytic_account account
                            WHERE account.id = (%(distribution)s)::text::int
                              AND account.plan_id = %(plan_id)s
                        )
                        ELSE NULL
                    END
                )""",
                distribution=distribution_sql,
                plan_id=plan.id,
            )
        return super()._field_to_sql(alias, fname, query)
