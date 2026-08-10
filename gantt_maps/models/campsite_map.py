from datetime import datetime, time, timedelta

from odoo import api, fields, models

from odoo.addons.camping_map_booking.models.camping_map_state import (
    STATE_FREE,
    STATE_OCCUPIED,
)

# Booking-status colors for occupied pitches on the Gantt map, keyed by
# planning.slot.x_booking_color (an Odoo palette index set from the booking's
# rental status). The values mirror the Planning gantt pill: fill is the gantt's
# o-gantt-colors mixin result `mix(base, white, 60%)`, stroke is the base palette
# color, hover is `mix(base, white, 70%)`. This keeps the map in sync with the
# schedule (grey = normal, yellow = check-in due, green = ongoing, blue =
# check-out due, red = attention, purple = internal).
_BOOKING_STATUS_COLORS = {
    0: {"fill": "#c7c7c7", "stroke": "#a2a2a2", "hover": "#bebebe"},  # grey - no focus
    1: {"fill": "#f58181", "stroke": "#ee2d2d", "hover": "#f36c6c"},  # red - attention
    3: {"fill": "#f1d677", "stroke": "#e8bb1d", "hover": "#efcf61"},  # yellow - check-in due
    4: {"fill": "#9abfeb", "stroke": "#5794dd", "hover": "#89b4e7"},  # blue - check-out due
    5: {"fill": "#c5a1bc", "stroke": "#9f628f", "hover": "#bc91b1"},  # purple - internal
    10: {"fill": "#a0dba8", "stroke": "#61c36e", "hover": "#90d599"},  # green - ongoing
}

# Legend entries for the Gantt map, in display order: (x_booking_color, label).
_BOOKING_STATUS_LEGEND = [
    (0, "Normal / returned"),
    (3, "Check-in due"),
    (10, "Ongoing"),
    (4, "Check-out due"),
    (1, "Attention (late)"),
    (5, "Internal"),
]


class CampsiteMap(models.Model):
    _inherit = "campsite.map"

    @api.model
    def get_gantt_map_preview(self, night):
        night_date = fields.Date.to_date(night)
        campsite_map = self.search([("active", "=", True)], order="name, id", limit=1)
        if not campsite_map or not night_date:
            return {"image_url": False, "shapes": []}

        start = datetime.combine(night_date, time(23, 45))
        end = datetime.combine(night_date + timedelta(days=1), time(0, 15))
        shapes = []
        for zone in campsite_map.zone_ids:
            state = zone._get_availability_state(False, start, end)
            zone_shapes = zone._get_map_shapes(state)
            # An occupied pitch is colored like its booking in the schedule, not
            # with the flat "occupied" color. Free pitches keep the state color.
            if state == STATE_OCCUPIED:
                booking_colors = self._get_zone_booking_colors(zone, start, end)
                if booking_colors:
                    for shape in zone_shapes:
                        shape["colors"] = booking_colors
            shapes += zone_shapes
        return {
            "image_url": campsite_map._image_url(),
            "shapes": shapes,
            "legend": self._get_gantt_legend(),
            "legend_position": campsite_map._legend_position(),
        }

    def _get_gantt_legend(self):
        """Legend items [{label, color}] matching the Gantt booking colors."""
        free_colors = self.env["camping.map.state"]._colors_for(STATE_FREE) or {}
        legend = [{"label": self.env._("Free"), "color": free_colors.get("fill", "#198754")}]
        legend += [
            {"label": self.env._(label), "color": _BOOKING_STATUS_COLORS[index]["fill"]}
            for index, label in _BOOKING_STATUS_LEGEND
        ]
        return legend

    def _get_zone_booking_colors(self, zone, start, end):
        """Gantt-pill colors of the booking occupying this zone on the night."""
        if not zone.resource_ids:
            return None
        slots = self.env["planning.slot"].search(
            [
                ("resource_id", "in", zone.resource_ids.ids),
                ("start_datetime", "<", end),
                ("end_datetime", ">", start),
            ]
        )
        if not slots:
            return None
        # x_booking_color is a non-stored computed field, so it can't be sorted
        # in the search. When several bookings overlap the zone, prefer one with
        # a flagged status (non-grey) over the neutral default.
        slot = sorted(slots, key=lambda s: (s.x_booking_color or 0) == 0)[0]
        color = slot.x_booking_color or 0
        return _BOOKING_STATUS_COLORS.get(color, _BOOKING_STATUS_COLORS[0])
