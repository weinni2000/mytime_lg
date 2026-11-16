from ._const import SELECTION_XMLIDS

RESTORE_SELECTION_XMLID_SQL = """
    INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
    SELECT
        'industry_real_estate',
        %(xmlid)s,
        'ir.model.fields.selection',
        selection.id,
        FALSE
    FROM ir_model_fields_selection AS selection
    JOIN ir_model_data AS field_xmlid
        ON field_xmlid.model = 'ir.model.fields'
       AND field_xmlid.res_id = selection.field_id
       AND field_xmlid.module = 'industry_real_estate'
       AND field_xmlid.name = %(field_xmlid)s
    WHERE selection.value = %(value)s
      AND NOT EXISTS (
          SELECT 1
          FROM ir_model_data AS selection_xmlid
          WHERE selection_xmlid.module = 'industry_real_estate'
            AND selection_xmlid.name = %(xmlid)s
      )
"""


def pre_init_hook(env):
    """Re-link the property selection rows to their XML IDs.

    Runs when this module is installed, i.e. before industry_real_estate is
    upgraded, so the upgrade updates the existing rows instead of creating
    duplicates.
    """
    for xmlid, field_xmlid, value in SELECTION_XMLIDS:
        env.cr.execute(
            RESTORE_SELECTION_XMLID_SQL,
            {"xmlid": xmlid, "field_xmlid": field_xmlid, "value": value},
        )
