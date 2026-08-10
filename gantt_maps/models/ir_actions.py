from odoo import fields, models


class IrActionsActWindowView(models.Model):
    _inherit = "ir.actions.act_window.view"

    view_mode = fields.Selection(
        selection_add=[("gantt_maps", "Gantt Maps")],
        ondelete={"gantt_maps": "cascade"},
    )
