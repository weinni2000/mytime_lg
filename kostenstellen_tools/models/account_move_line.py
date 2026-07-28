# Copyright 2026 mytime.click
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def action_open_form_view(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Journal Item"),
            "res_model": "account.move.line",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(self.env.ref("account.view_move_line_form").id, "form")],
            "target": "current",
        }
