def migrate(cr, version):
    """Hand the Studio-created ``x_studio_refresh`` field over to this module.

    The field was first created in Studio (xmlid in ``studio_customization``);
    the module now declares it itself, so re-key the existing xmlid instead of
    letting the data file try to create a second field with the same name.
    """
    cr.execute(
        """
        UPDATE ir_model_data
           SET module = 'city_tax',
               name = 'model_x_guests_line_x_studio_refresh',
               noupdate = false
         WHERE model = 'ir.model.fields'
           AND module = 'studio_customization'
           AND res_id IN (
               SELECT id FROM ir_model_fields
                WHERE model = 'x_guests_line' AND name = 'x_studio_refresh'
           )
           AND NOT EXISTS (
               SELECT 1 FROM ir_model_data
                WHERE module = 'city_tax'
                  AND name = 'model_x_guests_line_x_studio_refresh'
           )
        """
    )
