from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

DEFAULT_PITCH_TYPE_PRODUCT_VARIANTS = {
    66395: 7701,  # Electric optional grass tent pitch -> Zeltplatz (2P)
    59292: 7699,  # Gravel/sand touring pitch -> Stellplatz Wohnwagen (2P)
    60103: 7698,  # Electric optional grass campervan pitch -> Stellplatz Van (2P)
}


class PitchupSyncWizard(models.TransientModel):
    _name = "pitchup.sync.wizard"
    _description = "Map Products and Synchronize Pitchup"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    sync_unmapped_only = fields.Boolean()
    line_ids = fields.One2many("pitchup.sync.wizard.line", "wizard_id", string="Product Mappings")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if "line_ids" not in fields_list:
            return values
        company_id = values.get("company_id") or self.env.company.id
        mappings = self.env["pitchup.product.mapping"].search(
            [
                ("company_id", "=", company_id),
            ]
        )
        product_variants = dict(DEFAULT_PITCH_TYPE_PRODUCT_VARIANTS)
        product_template_by_pitch_type = {
            pitch_type_id: self.env["product.product"].browse(product_id).product_tmpl_id.id
            for pitch_type_id, product_id in product_variants.items()
            if self.env["product.product"].browse(product_id).exists()
        }
        product_template_by_pitch_type.update(
            {item.pitch_type_id: item.product_template_id.id for item in mappings}
        )
        names = {item.pitch_type_id: item.pitch_type_name for item in mappings}
        values["line_ids"] = [
            (
                0,
                0,
                {
                    "pitch_type_id": pitch_type_id,
                    "pitch_type_name": names.get(pitch_type_id),
                    "product_template_id": product_template_id,
                },
            )
            for pitch_type_id, product_template_id in product_template_by_pitch_type.items()
            if self.env["product.template"].browse(product_template_id).exists()
        ]
        return values

    def action_sync(self):
        self.ensure_one()
        pitch_type_ids = self.line_ids.mapped("pitch_type_id")
        if len(pitch_type_ids) != len(set(pitch_type_ids)):
            raise ValidationError(_("Each Pitchup pitch type may only be mapped once."))
        if any(not line.product_template_id for line in self.line_ids):
            raise ValidationError(_("Map every Pitchup pitch type to a local stay offer."))
        mapping_model = self.env["pitchup.product.mapping"]
        existing = mapping_model.search([("company_id", "=", self.company_id.id)])
        by_pitch_type = {mapping.pitch_type_id: mapping for mapping in existing}
        for line in self.line_ids:
            mapping = by_pitch_type.pop(line.pitch_type_id, mapping_model)
            values = {
                "pitch_type_id": line.pitch_type_id,
                "pitch_type_name": line.pitch_type_name,
                "product_template_id": line.product_template_id.id,
                "company_id": self.company_id.id,
            }
            mapping.write(values) if mapping else mapping_model.create(values)
        if not self.sync_unmapped_only:
            mapping_model.browse([item.id for item in by_pitch_type.values()]).unlink()
        return self.company_id.sudo().action_sync_pitchup_orders()


class PitchupSyncWizardLine(models.TransientModel):
    _name = "pitchup.sync.wizard.line"
    _description = "Pitchup Product Mapping Wizard Line"
    _order = "pitch_type_id"

    wizard_id = fields.Many2one("pitchup.sync.wizard", required=True, ondelete="cascade")
    pitch_type_id = fields.Integer(string="Pitchup Pitch Type ID", required=True)
    pitch_type_name = fields.Char(string="Pitchup Pitch Type")
    product_template_id = fields.Many2one(
        "product.template",
        string="Stay Offer",
        domain="[('x_is_a_room_offer', '=', True)]",
    )
