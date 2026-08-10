from odoo import _, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.camping_map_booking.models.camping_map_state import STATE_FREE


class SaleOrder(models.Model):
    _inherit = "sale.order"

    animal_ids = fields.One2many("animal", "sale_order_id", string="Dogs")
    pitch_resource_id = fields.Many2one("resource.resource", string="Pitch", copy=False, ondelete="restrict")
    pitch_planning_slot_id = fields.Many2one(
        "planning.slot", string="Pitch Slot", copy=False, readonly=True, ondelete="set null"
    )

    # pylint: disable=W8110
    def _cart_update_renting_period(self, start_date, end_date):
        """Clear a stale pitch selection when the rental period changes."""
        changed_orders = self.filtered(
            lambda order: order.rental_start_date != start_date or order.rental_return_date != end_date
        )
        super()._cart_update_renting_period(start_date, end_date)
        changed_orders.write({"pitch_resource_id": False, "pitch_planning_slot_id": False})

    def _get_pitch_sale_line(self):
        self.ensure_one()
        if not self.pitch_resource_id:
            return self.env["sale.order.line"]
        accommodation_lines = self.order_line.filtered(
            lambda line: not line.display_type and line.product_id.planning_role_id
        )
        matching_line = accommodation_lines.filtered(
            lambda line: line.product_id.planning_role_id in self.pitch_resource_id.role_ids
        )[:1]
        return matching_line or accommodation_lines[:1]

    def _validate_pitch_selection(self):
        self.ensure_one()
        if not self.company_id.x_use_camping_pitch_map:
            return
        if not self.pitch_resource_id:
            raise ValidationError(_("Please select an available pitch before confirming the order."))
        if not self.rental_start_date or not self.rental_return_date:
            raise ValidationError(_("The rental start and end are required to reserve a pitch."))

        vehicle_type = self.vehicle_ids[:1].category_id
        zone = self.env["camping.map.zone"].search(
            [("resource_ids", "in", self.pitch_resource_id.id), ("points", "!=", False)],
            limit=1,
        )
        if not zone:
            raise ValidationError(_("The selected pitch is not assigned to the campsite map."))
        if (
            zone._get_resource_state(
                self.pitch_resource_id,
                vehicle_type,
                self.rental_start_date,
                self.rental_return_date,
            )
            != STATE_FREE
        ):
            raise ValidationError(_("The selected pitch is no longer available for this stay."))
        if not self._get_pitch_sale_line():
            raise ValidationError(_("The selected pitch does not match any accommodation in this order."))

    def _action_confirm(self):
        pitch_orders = self.filtered(lambda order: order.company_id.x_use_camping_pitch_map and order.vehicle_ids)
        for order in pitch_orders:
            if order.pitch_resource_id:
                self.env.cr.execute(
                    "SELECT id FROM resource_resource WHERE id = %s FOR UPDATE",
                    (order.pitch_resource_id.id,),
                )
            order._validate_pitch_selection()

        result = super()._action_confirm()
        for order in pitch_orders:
            sale_line = order._get_pitch_sale_line()
            slot = sale_line.planning_slot_ids.filtered(lambda planning_slot: not planning_slot.start_datetime)[:1]
            if not slot:
                slot = sale_line.planning_slot_ids[:1]
            if not slot:
                raise ValidationError(_("No planning slot was generated for the selected pitch."))
            slot.write(
                {
                    "resource_id": order.pitch_resource_id.id,
                    "start_datetime": order.rental_start_date,
                    "end_datetime": order.rental_return_date,
                }
            )
            order.pitch_planning_slot_id = slot
        return result
