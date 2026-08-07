from odoo.tools import SQL


def migrate(cr, version):
    """Backfill is_rental_order/is_rental on orders created before this
    module started setting is_rental_order explicitly (see
    camping_guesty_sync.py). Those orders have rental_start_date set and a
    rentable product on the line, but is_rental_order stayed False because
    it was created outside the Rental app UI (no in_rental_app context),
    which hid rental_start_date on the form.
    """
    cr.execute(
        SQL(
            """
            UPDATE sale_order so
            SET is_rental_order = true
            WHERE so.is_rental_order IS NOT TRUE
              AND so.rental_start_date IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM sale_order_line sol
                  JOIN product_product pp ON pp.id = sol.product_id
                  JOIN product_template pt ON pt.id = pp.product_tmpl_id
                  WHERE sol.order_id = so.id AND pt.rent_ok = true
              )
            """
        )
    )

    cr.execute(
        SQL(
            """
            UPDATE sale_order_line sol
            SET is_rental = true
            FROM sale_order so, product_product pp, product_template pt
            WHERE sol.order_id = so.id
              AND pp.id = sol.product_id
              AND pt.id = pp.product_tmpl_id
              AND so.is_rental_order IS TRUE
              AND pt.rent_ok = true
              AND sol.is_rental IS NOT TRUE
            """
        )
    )
