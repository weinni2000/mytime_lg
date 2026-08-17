from odoo import _, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.camping_map_booking.models.camping_map_state import STATE_FREE

ADDITIONAL_GUEST_PRODUCT_XMLID = "camping_checkout.product_additional_guest"


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
        "camping_sale_order_pitch_slot_rel",
        "order_id",
        "slot_id",
        string="Pitch Slots",
        copy=False,
        readonly=True,
    )

    # pylint: disable=W8110
    def _cart_update_renting_period(self, start_date, end_date):
        """Clear a stale pitch selection when the rental period changes."""
        changed_orders = self.filtered(
            lambda order: order.rental_start_date != start_date or order.rental_return_date != end_date
        )
        super()._cart_update_renting_period(start_date, end_date)
        changed_orders.write({"pitch_resource_ids": [(5,)], "pitch_planning_slot_ids": [(5,)]})

    def _get_pitch_sale_line(self, pitch):
        """Accommodation line a given pitch belongs to (matched by planning role)."""
        self.ensure_one()
        accommodation_lines = self.order_line.filtered(
            lambda line: not line.display_type and line.product_id.planning_role_id
        )
        matching_line = accommodation_lines.filtered(
            lambda line: line.product_id.planning_role_id in pitch.role_ids
        )[:1]
        return matching_line or accommodation_lines[:1]

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

    def _validate_pitch_selection(self):
        self.ensure_one()
        if not self.company_id.x_use_camping_pitch_map:
            return
        if not self.pitch_resource_ids:
            raise ValidationError(_("Please select at least one available pitch before confirming the order."))
        if not self.rental_start_date or not self.rental_return_date:
            raise ValidationError(_("The rental start and end are required to reserve a pitch."))

        vehicle_type = self.vehicle_ids[:1].category_id
        for pitch in self.pitch_resource_ids:
            zone = self.env["camping.map.zone"].search(
                [("resource_ids", "in", pitch.id), ("points", "!=", False)],
                limit=1,
            )
            if not zone:
                raise ValidationError(_("The pitch %s is not assigned to the campsite map.", pitch.name))
            if (
                zone._get_resource_state(
                    pitch,
                    vehicle_type,
                    self.rental_start_date,
                    self.rental_return_date,
                )
                != STATE_FREE
            ):
                raise ValidationError(_("The pitch %s is no longer available for this stay.", pitch.name))
            if not self._get_pitch_sale_line(pitch):
                raise ValidationError(
                    _("The pitch %s does not match any accommodation in this order.", pitch.name)
                )

    def _action_confirm(self):
        pitch_orders = self.filtered(lambda order: order.company_id.x_use_camping_pitch_map and order.vehicle_ids)
        for order in pitch_orders:
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
            order.pitch_planning_slot_ids = [(6, 0, booked_slots.ids)]
        return result
