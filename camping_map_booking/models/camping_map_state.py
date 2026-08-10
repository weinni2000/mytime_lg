from odoo import api, fields, models

# Canonical availability-state codes. These are the single source of truth for
# the state identifiers used by the availability logic and are mirrored by the
# `code` of the `camping.map.state` records shipped in data. Import these
# constants instead of hard-coding the strings.
STATE_FREE = "free"
STATE_OCCUPIED = "occupied"
STATE_NOT_SUITABLE = "not_suitable"


class CampingMapState(models.Model):
    _name = "camping.map.state"
    _description = "Camping Map Availability State"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Technical identifier used by the availability logic (e.g. free, occupied).",
    )
    color = fields.Char(
        string="Fill Color",
        required=True,
        help="Main fill color of a zone in this state, as a CSS color (e.g. #198754).",
    )
    stroke_color = fields.Char(
        string="Border Color",
        help="Outline color of a zone in this state. Defaults to the fill color.",
    )
    hover_color = fields.Char(
        string="Hover Fill Color",
        help="Fill color when the zone is hovered or selected. Defaults to the fill color.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Each camping map state code must be unique."),
    ]

    @api.model
    def _get_frontend_map(self):
        """code -> {fill, stroke, hover, label} for every active state.

        Single source of truth for how availability states are labelled and
        colored on the campsite map, both in the backend preview and on the
        website pitch step.
        """
        result = {}
        for state in self.sudo().search([]):
            result[state.code] = {
                "fill": state.color or "",
                "stroke": state.stroke_color or state.color or "",
                "hover": state.hover_color or state.color or "",
                "label": state.name or "",
            }
        return result

    @api.model
    def _colors_for(self, code):
        """{fill, stroke, hover} for a single state code, or None."""
        if not code:
            return None
        state = self.sudo().search([("code", "=", code)], limit=1)
        if not state:
            return None
        return {
            "fill": state.color or "",
            "stroke": state.stroke_color or state.color or "",
            "hover": state.hover_color or state.color or "",
        }
