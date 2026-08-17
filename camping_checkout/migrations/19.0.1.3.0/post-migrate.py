import logging

_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    """Carry the legacy single pitch/slot selection into the new many2many fields."""
    # Preserve the previous surcharge threshold: included persons used to be the
    # product's "Max Guests", so seed the new field from it.
    if _column_exists(cr, "product_template", "x_included_persons") and _column_exists(
        cr, "product_template", "x_max_guest"
    ):
        cr.execute("UPDATE product_template SET x_included_persons = x_max_guest WHERE x_max_guest IS NOT NULL")
        _logger.info("camping_checkout: seeded x_included_persons from x_max_guest")

    if _column_exists(cr, "sale_order", "pitch_resource_id"):
        cr.execute(
            """
            INSERT INTO camping_sale_order_pitch_rel (order_id, resource_id)
            SELECT so.id, so.pitch_resource_id
            FROM sale_order so
            WHERE so.pitch_resource_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM camping_sale_order_pitch_rel r
                  WHERE r.order_id = so.id AND r.resource_id = so.pitch_resource_id
              )
            """
        )
        _logger.info("camping_checkout: migrated pitch_resource_id -> pitch_resource_ids")

    if _column_exists(cr, "sale_order", "pitch_planning_slot_id"):
        cr.execute(
            """
            INSERT INTO camping_sale_order_pitch_slot_rel (order_id, slot_id)
            SELECT so.id, so.pitch_planning_slot_id
            FROM sale_order so
            WHERE so.pitch_planning_slot_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM camping_sale_order_pitch_slot_rel r
                  WHERE r.order_id = so.id AND r.slot_id = so.pitch_planning_slot_id
              )
            """
        )
        _logger.info("camping_checkout: migrated pitch_planning_slot_id -> pitch_planning_slot_ids")
