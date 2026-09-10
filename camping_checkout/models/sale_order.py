from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.camping_map_booking.models.camping_map_state import STATE_FREE

ADDITIONAL_GUEST_PRODUCT_XMLID = "camping_checkout.product_additional_guest"
EXTRA_VEHICLE_PRODUCT_XMLID = "camping_checkout.product_extra_vehicle"


class SaleOrder(models.Model):
    _inherit = "sale.order"

    animal_ids = fields.One2many("animal", "sale_order_id", string="Dogs")
    pitch_resource_ids = fields.Many2many(
        "resource.resource",
        "camping_sale_order_pitch_rel",
        "order_id",
        "resource_id",
        string="Pitches",
        copy=False,
    )
    pitch_planning_slot_ids = fields.Many2many(
        "planning.slot",
        compute="_compute_pitch_planning_slot_ids",
        string="Pitch Slots",
    )

    @api.depends("order_line.planning_slot_ids")
    def _compute_pitch_planning_slot_ids(self):
        # Reads straight from the lines' planning slots rather than filtering
        # by pitch_resource_ids: most orders never populate that field (it's
        # only set by the website map picker), while the slots themselves are
        # always there regardless of which flow assigned the pitch.
        for order in self:
            order.pitch_planning_slot_ids = order.order_line.planning_slot_ids

    # pylint: disable=W8110
    def _cart_update_renting_period(self, start_date, end_date):
        """Clear a stale pitch selection when the rental period changes."""
        changed_orders = self.filtered(
            lambda order: order.rental_start_date != start_date or order.rental_return_date != end_date
        )
        super()._cart_update_renting_period(start_date, end_date)
        changed_orders.write({"pitch_resource_ids": [(5,)]})

    def _get_pitch_product(self, pitch):
        """Accommodation product matching a given pitch's planning role."""
        return (
            self.env["product.template"]
            .search([("planning_role_id", "in", pitch.role_ids.ids)], limit=1)
            .product_variant_id
        )

    def _find_pitch_sale_line(self, pitch):
        """Existing accommodation line matching a pitch's planning role, if any.

        Read-only (never creates a line) - shared by _get_pitch_sale_line
        (which does create one, for cart mutation) and _get_pitch_names_by_line
        (for display, called while just rendering a page).
        """
        self.ensure_one()
        accommodation_lines = self.order_line.filtered(
            lambda line: not line.display_type and line.product_id.planning_role_id
        )
        return accommodation_lines.filtered(lambda line: line.product_id.planning_role_id in pitch.role_ids)[:1]

    def _get_pitch_sale_line(self, pitch):
        """Accommodation line a given pitch belongs to (matched by planning role).

        Creates the line for the pitch's own product if the order doesn't have
        one yet, so pitches of different types (e.g. a tent spot and a caravan
        spot) each land on their own product line instead of all being lumped
        onto whichever accommodation line already happens to be in the cart.
        """
        self.ensure_one()
        matching_line = self._find_pitch_sale_line(pitch)
        if matching_line:
            return matching_line

        product = self._get_pitch_product(pitch)
        if not product:
            return self.order_line.filtered(
                lambda line: not line.display_type and line.product_id.planning_role_id
            )[:1]

        self._cart_add(
            product_id=product.id,
            quantity=1,
            start_date=self.rental_start_date,
            end_date=self.rental_return_date,
        )
        return self._cart_find_product_line(product.id, uom_id=product.uom_id.id)[:1]

    def _get_pitch_names_by_line(self):
        """{accommodation sale.order.line: pitch names shown on it, comma-separated}.

        Read-only display helper for the checkout order summary - unlike
        _pitch_lines_map, this never creates a line, so it's safe to call
        on every page render instead of only after a form submit.
        """
        self.ensure_one()
        mapping = {}
        for pitch in self.pitch_resource_ids:
            line = self._find_pitch_sale_line(pitch)
            if line:
                mapping[line] = mapping.get(line, self.env["resource.resource"]) | pitch
        return {line: ", ".join(pitches.mapped("name")) for line, pitches in mapping.items()}

    def _update_additional_guest_charge(self):
        """(Re)price the additional-guest surcharge.

        Every accommodation includes ``x_included_persons`` guests in its price;
        the included headcount scales with the line quantity, so with several
        pitches it is ``included_persons x qty`` (e.g. 2 pitches x 2 = 4). Each
        guest beyond the total included headcount adds one additional-guest unit.
        Safe to call again whenever the guest count or pitch quantity changes.
        """
        self.ensure_one()
        extra_product = self.env.ref(ADDITIONAL_GUEST_PRODUCT_XMLID, raise_if_not_found=False)
        if not extra_product:
            return
        accommodation_lines = self.order_line.filtered(
            lambda line: line.product_id.product_tmpl_id.x_additional_guest_product_id
        )
        if not accommodation_lines:
            return
        included_total = sum(
            line.product_uom_qty * line.product_id.x_included_persons for line in accommodation_lines
        )
        extra_qty = max(len(self.x_guest_line_ids) - included_total, 0)
        self._set_camping_extra_quantity(extra_product, extra_qty)

    def _update_extra_vehicle_charge(self):
        """(Re)price the extra-vehicle surcharge.

        Each pitch includes 1 vehicle; the included count scales with the
        accommodation quantity (2 pitches = 2 included vehicles), same as
        ``_update_additional_guest_charge`` does for guests. Every vehicle
        beyond that total adds one extra-vehicle unit. Safe to call again
        whenever the vehicle count or pitch quantity changes.
        """
        self.ensure_one()
        extra_product = self.env.ref(EXTRA_VEHICLE_PRODUCT_XMLID, raise_if_not_found=False)
        if not extra_product:
            return
        accommodation_lines = self.order_line.filtered(
            lambda line: not line.display_type and line.product_id.planning_role_id
        )
        included_total = sum(line.product_uom_qty for line in accommodation_lines)
        extra_qty = max(len(self.vehicle_ids) - included_total, 0)
        self._set_camping_extra_quantity(extra_product, extra_qty)

    def _set_camping_extra_quantity(self, product, quantity):
        self.ensure_one()
        existing_line = self._cart_find_product_line(product.id, uom_id=product.uom_id.id)[:1]
        if existing_line:
            self._cart_update_line_quantity(line_id=existing_line.id, quantity=quantity)
        elif quantity > 0:
            self._cart_add(
                product_id=product.id,
                quantity=quantity,
                start_date=self.rental_start_date,
                end_date=self.rental_return_date,
            )

    def _pitch_lines_map(self):
        """{accommodation sale.order.line: resource.resource(pitches on that line)}."""
        self.ensure_one()
        mapping = {}
        for pitch in self.pitch_resource_ids:
            line = self._get_pitch_sale_line(pitch)
            if not line:
                continue
            mapping[line] = mapping.get(line, self.env["resource.resource"]) | pitch
        return mapping

    def _pitch_is_free(self, pitch):
        """Whether ``pitch`` has no other order's planning slot overlapping this stay.

        Excludes this order's own planning slots: a channel sync (e.g. Guesty)
        already creates its slot for this stay before calling action_confirm(),
        which would otherwise always self-collide.
        """
        self.ensure_one()
        overlap = (
            [
                ("start_datetime", "<", self.rental_return_date),
                ("end_datetime", ">", self.rental_start_date),
            ]
            if self.rental_return_date > self.rental_start_date
            else [
                ("start_datetime", "<=", self.rental_start_date),
                ("end_datetime", ">", self.rental_start_date),
            ]
        )
        return not self.env["planning.slot"].search_count(
            [("resource_id", "=", pitch.id), ("sale_order_id", "!=", self.id), *overlap]
        )

    def _auto_assign_pitches(self):
        """Pick the next available pitch per accommodation line when none was selected.

        Candidates come from the line's product (``x_resource_ids``, i.e. its
        planning role's resources) rather than the visual map, since a pitch is
        derived from the product, not from being plotted on the map.
        """
        self.ensure_one()
        if self.pitch_resource_ids or not self.rental_start_date or not self.rental_return_date:
            return
        accommodation_lines = self.order_line.filtered(
            lambda line: not line.display_type and line.product_id.planning_role_id
        )
        vehicle_type = self.vehicle_ids[:1].category_id
        chosen = self.env["resource.resource"]
        for line in accommodation_lines:
            needed = int(line.product_uom_qty)
            for resource in line.product_id.x_resource_ids - chosen:
                if needed <= 0:
                    break
                allowed_vehicle_types = resource.role_ids.allowed_vehicle_type_ids
                if vehicle_type and allowed_vehicle_types and vehicle_type not in allowed_vehicle_types:
                    continue
                if not self._pitch_is_free(resource):
                    continue
                chosen |= resource
                needed -= 1
        if chosen:
            self.pitch_resource_ids = [(6, 0, chosen.ids)]

    def _validate_pitch_selection(self):
        self.ensure_one()
        if not self.company_id.x_use_camping_pitch_map:
            return
        if not self.pitch_resource_ids:
            raise ValidationError(_("Please select at least one available pitch before confirming the order."))
        if not self.rental_start_date or not self.rental_return_date:
            raise ValidationError(_("The rental start and end are required to reserve a pitch."))

        zone_model = self.env["camping.map.zone"]
        for pitch in self.pitch_resource_ids:
            if not self._get_pitch_sale_line(pitch):
                raise ValidationError(
                    _("The pitch %s does not match any accommodation in this order.", pitch.name)
                )
            if not self.vehicle_ids:
                # No vehicle means the pitch wasn't picked from the interactive
                # map (e.g. it's a fixed, channel-synced unit like the Tiny
                # House), so it isn't required to be plotted on that map or
                # vehicle-suitability-checked; still guard against double-booking.
                if not self._pitch_is_free(pitch):
                    raise ValidationError(_("The pitch %s is no longer available for this stay.", pitch.name))
                continue
            zone = zone_model.search(
                [("resource_ids", "in", pitch.id), ("points", "!=", False)],
                limit=1,
            )
            if not zone:
                raise ValidationError(_("The pitch %s is not assigned to the campsite map.", pitch.name))
            if (
                zone._get_resource_state(
                    pitch,
                    None,
                    self.rental_start_date,
                    self.rental_return_date,
                )
                != STATE_FREE
            ):
                raise ValidationError(_("The pitch %s is no longer available for this stay.", pitch.name))

    def _split_guest_lines_to_pitches(self):
        """Assign each guest line without a room yet to one of the order's pitches.

        Reads the pitches from the accommodation lines' planning slots rather
        than ``pitch_resource_ids``: most confirmed orders never go through the
        website map picker that fills ``pitch_resource_ids`` (backend bookings,
        channel-synced orders, ...) and instead get a pitch dropped onto their
        line's planning slot directly (Gantt/planning view), so the slot is the
        source that is actually populated in the vast majority of cases.

        Fills pitches in order, up to each accommodation's ``x_included_persons``
        capacity, before moving on to the next pitch. Runs on check-in (see
        ``data/base_automation.xml``) so it applies regardless of which flow
        triggered the check-in (Pickup button, guest registration, channel sync).
        """
        for order in self:
            accommodation_lines = order.order_line.filtered(
                lambda line: not line.display_type and line.product_id.planning_role_id
            )
            slots = []
            for line in accommodation_lines:
                capacity = line.product_id.x_included_persons or 1
                for resource in line.planning_slot_ids.resource_id:
                    slots.append([resource, capacity])
            if not slots:
                continue
            guests = order.x_guest_line_ids.filtered(lambda guest: not guest.x_room_resource_id)
            if not guests:
                continue
            index = 0
            for guest in guests:
                while slots[index][1] <= 0 and index < len(slots) - 1:
                    index += 1
                guest.x_room_resource_id = slots[index][0].id
                slots[index][1] -= 1

    def _action_confirm(self):
        pitch_orders = self.filtered(lambda order: order.company_id.x_use_camping_pitch_map)
        for order in pitch_orders:
            order._auto_assign_pitches()
            for pitch in order.pitch_resource_ids:
                self.env.cr.execute(
                    "SELECT id FROM resource_resource WHERE id = %s FOR UPDATE",
                    (pitch.id,),
                )
            order._validate_pitch_selection()

        result = super()._action_confirm()
        for order in pitch_orders:
            booked_slots = self.env["planning.slot"]
            for line, pitches in order._pitch_lines_map().items():
                # Reuse the line's existing (auto-generated) slots first, filling
                # the still-unassigned ones before the assigned ones, then create
                # extra slots so every pitch gets its own reservation.
                available_slots = list(
                    line.planning_slot_ids.sorted(key=lambda slot: (bool(slot.start_datetime), slot.id))
                )
                for index, pitch in enumerate(pitches):
                    if index < len(available_slots):
                        slot = available_slots[index]
                    else:
                        slot = self.env["planning.slot"].create(line._planning_slot_values())
                    slot.write(
                        {
                            "resource_id": pitch.id,
                            "start_datetime": order.rental_start_date,
                            "end_datetime": order.rental_return_date,
                        }
                    )
                    booked_slots |= slot
            if not booked_slots:
                raise ValidationError(_("No planning slot was generated for the selected pitches."))
        return result
