from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Remove the obsolete Y model after its records have been migrated."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    legacy_model = env["ir.model"].search([("model", "=", "y_guests_line")])
    if legacy_model:
        cr.execute("UPDATE ir_model SET state = 'manual' WHERE id = %s", (legacy_model.id,))
        legacy_model.invalidate_recordset(["state"])
        legacy_model.with_context(_force_unlink=True).unlink()

    env["ir.sequence"].search([("code", "=", "y_guests_line.group")]).unlink()
    cr.execute("DROP TABLE IF EXISTS resource_resource_y_guests_line_rel CASCADE")
    cr.execute("DROP TABLE IF EXISTS y_guests_line CASCADE")
