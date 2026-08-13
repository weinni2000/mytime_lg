from datetime import datetime, time, timedelta

from odoo import api, fields, models

from odoo.addons.camping_map_booking.models.camping_map_state import STATE_OCCUPIED

# Legend entries for the Gantt map, in display order: (x_booking_color, label).
# The colours themselves are resolved in CSS from the very same palette the
# Gantt pills use (the ``o_gantt_color_<n>`` classes, keyed by
# planning.slot.x_booking_color), so the map matches the schedule in both light
# and dark themes without hardcoding a single colour here. See gantt_maps.scss.
_BOOKING_STATUS_LEGEND = [
    (0, "Normal / returned"),
    (3, "Check-in due"),
    (10, "Ongoing"),
    (4, "Check-out due"),
    (1, "Attention (late)"),
    (5, "Internal"),
]


def _booking_color_class(index):
    """CSS class mirroring the Gantt pill colour for a booking-status index."""
    return "o_gantt_color_%d" % int(index or 0)


# CSS class for the unallocated (free) share of a pitch, rendered white.
_FREE_COLOR_CLASS = "o_camping_map_zone_free"


class CampsiteMap(models.Model):
    _inherit = "campsite.map"

    @api.model
    def get_gantt_map_preview(self, start, end=None, show_free=False):
        """Availability shapes for the map, for a single night or a date range.

        Two ways to call it:

        * ``start`` alone is a **point in time** (a datetime): each pitch is
          coloured by the booking occupying it at that exact instant, or flagged
          empty when nothing is booked.
        * ``start`` + ``end`` is a **date range**: each pitch is filled
          proportionally to the booking types that occupy it over the nights
          ``[start, end)`` (see ``_get_zone_occupancy_shapes``).

        When ``show_free`` is set, the unallocated share of each pitch is shown
        too, as a proportional white slice (e.g. 50% free -> half the pitch
        white); otherwise only the booked share is coloured.

        Colours are not computed here: each shape carries a Gantt colour class
        (``o_gantt_color_<n>``) that CSS resolves from the Gantt palette, so the
        map matches the pills in any theme.
        """
        campsite_map = self.search([("active", "=", True)], order="name, id", limit=1)
        if not campsite_map:
            return {"image_url": False, "shapes": []}

        shapes = []
        if end:
            start_date = fields.Date.to_date(start)
            end_date = fields.Date.to_date(end)
            if start_date:
                if end_date and end_date > start_date:
                    nights = [
                        start_date + timedelta(days=offset) for offset in range((end_date - start_date).days)
                    ]
                else:
                    nights = [start_date]
                for zone in campsite_map.zone_ids:
                    shapes += self._get_zone_occupancy_shapes(zone, nights, show_free)
        else:
            point = fields.Datetime.to_datetime(start)
            if point:
                for zone in campsite_map.zone_ids:
                    shapes += self._get_zone_point_shapes(zone, point, show_free)

        return {
            "image_url": campsite_map._image_url(),
            "shapes": shapes,
            "legend": self._get_gantt_legend(),
            "legend_position": campsite_map._legend_position(),
            "label_scale": campsite_map.label_scale or 1.0,
        }

    def _get_zone_point_shapes(self, zone, point, show_free=False):
        """Map shape(s) for ``zone`` coloured by the booking on it at ``point``."""
        shapes = zone._get_map_shapes()
        if not shapes:
            return []

        occupied = bool(zone.resource_ids) and (zone._get_availability_state(False, point) == STATE_OCCUPIED)
        if occupied:
            slots = self.env["planning.slot"].search(
                [
                    ("resource_id", "in", zone.resource_ids.ids),
                    ("start_datetime", "<=", point),
                    ("end_datetime", ">", point),
                ]
            )
            color_class = _booking_color_class(self._pick_booking_color_index(slots))
            empty = False
        elif show_free and zone.resource_ids:
            # Free at this instant, shown white when the option is on.
            color_class = _FREE_COLOR_CLASS
            empty = False
        else:
            color_class = False
            empty = True
        for shape in shapes:
            shape["color_class"] = color_class
            shape["segments"] = []
            shape["empty"] = empty
        return shapes

    def _get_zone_occupancy_shapes(self, zone, nights, show_free=False):
        """Map shape(s) for ``zone`` coloured by which booking types occupy it.

        The booking colours are shown in proportion to each other. When
        ``show_free`` is set the unallocated nights are added as a proportional
        white slice and every share is normalised over the whole range;
        otherwise only booked nights count. A pitch with no resource (nothing to
        measure), or with nothing booked while ``show_free`` is off, is flagged
        ``empty``.
        """
        shapes = zone._get_map_shapes()
        if not shapes:
            return []

        # Tally the booked nights per Gantt colour index.
        counts = {}
        for night in zone.resource_ids and nights or []:
            night_start = datetime.combine(night, time(23, 45))
            night_end = datetime.combine(night + timedelta(days=1), time(0, 15))
            if zone._get_availability_state(False, night_start, night_end) != STATE_OCCUPIED:
                continue
            index = self._get_zone_booking_color_index(zone, night_start, night_end)
            counts[index] = counts.get(index, 0) + 1

        total = len(nights) if zone.resource_ids else 0
        booked = sum(counts.values())
        free = total - booked
        # Denominator: the whole range when showing free time, else only the
        # booked nights (the free share is ignored).
        denom = total if show_free else booked
        if not denom:
            # No resource, or nothing booked and the free share is hidden.
            for shape in shapes:
                shape["color_class"] = False
                shape["segments"] = []
                shape["empty"] = True
            return shapes

        # Biggest booked share first (drives the polygon's stroke), then the
        # white free slice last.
        ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        segments = [
            {"color_class": _booking_color_class(index), "fraction": count / denom} for index, count in ordered
        ]
        if show_free and free > 0:
            segments.append({"color_class": _FREE_COLOR_CLASS, "fraction": free / denom})

        dominant = _booking_color_class(ordered[0][0]) if ordered else _FREE_COLOR_CLASS
        for shape in shapes:
            shape["color_class"] = dominant
            shape["segments"] = segments
            shape["empty"] = False
        return shapes

    def _get_gantt_legend(self):
        """Legend items [{label, color_class}] matching the Gantt booking colours.

        Free (green) is intentionally omitted: the map only colours booked
        types, so a "Free" swatch would never appear on a pitch.
        """
        return [
            {"label": self.env._(label), "color_class": _booking_color_class(index)}
            for index, label in _BOOKING_STATUS_LEGEND
        ]

    def _get_zone_booking_color_index(self, zone, start, end):
        """Gantt colour index of the booking occupying this zone on the night."""
        if not zone.resource_ids:
            return 0
        slots = self.env["planning.slot"].search(
            [
                ("resource_id", "in", zone.resource_ids.ids),
                ("start_datetime", "<", end),
                ("end_datetime", ">", start),
            ]
        )
        return self._pick_booking_color_index(slots)

    def _pick_booking_color_index(self, slots):
        """Gantt colour index (x_booking_color) for a set of overlapping slots."""
        if not slots:
            return 0
        # x_booking_color is a non-stored computed field, so it can't be sorted
        # in the search. When several bookings overlap the zone, prefer one with
        # a flagged status (non-neutral) over the neutral default.
        slot = sorted(slots, key=lambda s: (s.x_booking_color or 0) == 0)[0]
        return slot.x_booking_color or 0
