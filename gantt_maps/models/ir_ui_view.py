from odoo import fields, models


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    type = fields.Selection(selection_add=[("gantt_maps", "Gantt Maps")])

    def _validate_tag_gantt_maps(self, node, name_manager, node_info):
        return self._validate_tag_gantt(node, name_manager, node_info)

    def _get_view_fields(self, view_type, models):
        if view_type == "gantt_maps":
            view_type = "gantt"
        return super()._get_view_fields(view_type, models)

    def _get_view_info(self):
        return {
            "gantt_maps": {"icon": "fa fa-tasks"},
        } | super()._get_view_info()

    def _is_qweb_based_view(self, view_type):
        return view_type == "gantt_maps" or super()._is_qweb_based_view(view_type)
