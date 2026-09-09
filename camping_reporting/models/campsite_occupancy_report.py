from odoo import fields, models, tools


class CampsiteOccupancyReport(models.Model):
    _name = "campsite.occupancy.report"
    _description = "Campsite Occupancy Report"
    _auto = False
    _order = "date desc, pitch_id, booking_id"

    date = fields.Date(readonly=True)
    pitch_id = fields.Many2one("resource.resource", string="Pitch", readonly=True)
    role_id = fields.Many2one("planning.role", string="Planning Role", readonly=True)
    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    sale_channel_id = fields.Many2one("sale.channel", string="Sale Channel", readonly=True)
    booking_id = fields.Many2one("sale.order", string="Booking", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    adults = fields.Integer(readonly=True)
    children = fields.Integer(readonly=True)
    guests = fields.Integer(readonly=True)
    occupied_pitch = fields.Integer(string="Occupied Pitches", readonly=True)
    rent_amount = fields.Monetary(readonly=True)
    ortstaxe_amount = fields.Monetary(readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
                CREATE OR REPLACE VIEW {self._table} AS (
                    SELECT
                        (ps.id::bigint * 100000 +
                            (occupied_day.day::date - DATE '2000-01-01'))::bigint AS id,
                        occupied_day.day::date AS date,
                        ps.resource_id AS pitch_id,
                        ps.role_id AS role_id,
                        sol.product_id AS product_id,
                        so.sale_channel_id AS sale_channel_id,
                        so.id AS booking_id,
                        so.company_id AS company_id,
                        company.currency_id AS currency_id,
                        COALESCE(guest_totals.guests, 0)
                            - COALESCE(guest_totals.children, 0) AS adults,
                        COALESCE(guest_totals.children, 0) AS children,
                        COALESCE(guest_totals.guests, 0) AS guests,
                        1 AS occupied_pitch,
                        ROUND(
                            sol.price_subtotal
                                / COUNT(*) OVER (PARTITION BY sol.id),
                            2
                        ) AS rent_amount,
                        ROUND(
                            COALESCE(tax_line.amount, 0)
                                / COUNT(*) OVER (PARTITION BY so.id),
                            2
                        ) AS ortstaxe_amount
                    FROM planning_slot ps
                    JOIN sale_order_line sol ON sol.id = ps.sale_line_id
                    JOIN sale_order so ON so.id = sol.order_id
                    LEFT JOIN sale_channel channel
                        ON channel.id = so.sale_channel_id
                    JOIN res_company company ON company.id = so.company_id
                    JOIN resource_calendar calendar
                        ON calendar.id = company.resource_calendar_id
                    LEFT JOIN LATERAL (
                        SELECT SUM(tax_line_item.price_subtotal) AS amount
                        FROM sale_order_line tax_line_item
                        WHERE tax_line_item.order_id = so.id
                          AND tax_line_item.product_id
                              = company.x_local_tax_product_id
                    ) tax_line ON TRUE
                    CROSS JOIN LATERAL generate_series(
                        (ps.start_datetime AT TIME ZONE 'UTC'
                            AT TIME ZONE calendar.tz)::date,
                        (ps.end_datetime AT TIME ZONE 'UTC'
                            AT TIME ZONE calendar.tz)::date,
                        INTERVAL '1 day'
                    ) AS occupied_day(day)
                    LEFT JOIN LATERAL (
                        SELECT
                            COUNT(*)::integer AS guests,
                            COUNT(*) FILTER (
                                WHERE partner.birthdate_date IS NOT NULL
                                  AND occupied_day.day::date
                                      < partner.birthdate_date + INTERVAL '15 years'
                            )::integer AS children
                        FROM x_guests_line guest_line
                        LEFT JOIN res_partner partner
                            ON partner.id = guest_line.x_guest_partner_id
                        WHERE guest_line.x_sale_order_id = so.id
                          AND guest_line.x_room_resource_id = ps.resource_id
                    ) guest_totals ON TRUE
                    WHERE ps.resource_id IS NOT NULL
                      AND ps.start_datetime IS NOT NULL
                      AND ps.end_datetime IS NOT NULL
                      AND ps.end_datetime > ps.start_datetime
                      AND ((occupied_day.day::date + TIME '23:45')
                          AT TIME ZONE calendar.tz AT TIME ZONE 'UTC')
                          >= ps.start_datetime
                      AND ((occupied_day.day::date + TIME '23:45')
                          AT TIME ZONE calendar.tz AT TIME ZONE 'UTC')
                          < ps.end_datetime
                      AND so.state IN ('sale', 'done')
                      AND COALESCE(channel.name, '')
                          NOT IN ('Tiny House', 'Tiny Away')
                )
            """
        )
