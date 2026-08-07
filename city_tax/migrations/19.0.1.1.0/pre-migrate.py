from psycopg2.extras import Json


def migrate(cr, version):
    """Move the former Y guest lines into the canonical Booking Engine model."""
    cr.execute("SELECT to_regclass('public.y_guests_line')")
    if not cr.fetchone()[0]:
        return

    cr.execute("ALTER TABLE x_guests_line ADD COLUMN IF NOT EXISTS x_arrival_date_manual date")
    cr.execute("ALTER TABLE x_guests_line ADD COLUMN IF NOT EXISTS x_departure_date_manual date")
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS guest_tax_message_x_guests_line_rel (
            message_id integer NOT NULL,
            guest_line_id integer NOT NULL,
            PRIMARY KEY (message_id, guest_line_id)
        )
        """
    )
    cr.execute(
        """
        SELECT y.id, y.create_uid, y.write_uid, y.create_date, y.write_date,
               y.x_sequence, y.x_name, y.x_sale_order_id, y.x_guest_partner_id,
               y.x_room_resource_id, y.x_main_guest, y.x_refresh,
               y.x_arrival_date,
               COALESCE(y.x_arrival_date_manual, message.x_arrival_date),
               y.x_planned_departure_date, y.x_departure_date,
               COALESCE(y.x_departure_date_manual, message.x_departure_date),
               y.x_save_as_contact, y.x_guest_name, y.x_guest_title_id,
               y.x_anrede, y.x_guest_lang, y.x_guest_country_id,
               y.x_guest_nationality, y.x_guest_zip, y.x_guest_city,
               y.x_guest_street, y.x_guest_document_type,
               y.x_guest_document_number, y.x_guest_document_date,
               y.x_guest_document_authority, y.x_guest_birthdate,
               y.x_guest_marketing_consent, y.x_group_id
          FROM y_guests_line y
          LEFT JOIN guest_tax_message message ON message.id = y.x_group_id
         ORDER BY y.id
        """
    )
    rows = cr.fetchall()
    insert_columns = (
        "create_uid",
        "write_uid",
        "create_date",
        "write_date",
        "x_sequence",
        "x_name",
        "x_sale_order_id",
        "x_guest_partner_id",
        "x_room_resource_id",
        "x_main_guest",
        "x_refresh",
        "x_arrival_date",
        "x_arrival_date_manual",
        "x_planned_departure_date",
        "x_departure_date",
        "x_departure_date_manual",
        "x_save_as_contact",
        "x_guest_name",
        "x_guest_title_id",
        "x_anrede",
        "x_guest_lang",
        "x_guest_country_id",
        "x_guest_nationality",
        "x_guest_zip",
        "x_guest_city",
        "x_guest_street",
        "x_guest_document_type",
        "x_guest_document_number",
        "x_guest_document_date",
        "x_guest_document_authority",
        "x_guest_birthdate",
        "x_guest_marketing_consent",
    )
    placeholders = ", ".join(["%s"] * len(insert_columns))
    for row in rows:
        old_id, *values, message_id = row
        values[5] = Json({"en_US": values[5]}) if values[5] else None
        cr.execute(
            f"INSERT INTO x_guests_line ({', '.join(insert_columns)}) " f"VALUES ({placeholders}) RETURNING id",
            values,
        )
        new_id = cr.fetchone()[0]
        if message_id:
            cr.execute(
                """
                INSERT INTO guest_tax_message_x_guests_line_rel (message_id, guest_line_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
                """,
                (message_id, new_id),
            )
