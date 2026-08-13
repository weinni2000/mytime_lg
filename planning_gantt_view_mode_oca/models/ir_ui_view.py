from odoo import models


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    def _get_view_info(self):
        # web_timeline ships the timeline view with the "fa fa-tasks" icon,
        # which is identical to the gantt view icon. On the booking Schedule
        # both view types are available, so the two switcher buttons become
        # indistinguishable. Give timeline its own icon so it is recognizable.
        info = super()._get_view_info()
        if "timeline" in info:
            info["timeline"] = {**info["timeline"], "icon": "fa fa-sliders"}
        return info
