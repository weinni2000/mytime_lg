from odoo import fields, models


class FlowerCalculatorMappingWizard(models.TransientModel):
    _name = "flower.calculator.mapping.wizard"
    _description = "Sync Flower Names to Product Mapping"

    sale_order_id = fields.Many2one("sale.order", required=True)
    new_chatgpt_names = fields.Text(compute="_compute_new_chatgpt_names")

    def _get_new_flower_names(self):
        self.ensure_one()
        flowers = (self.sale_order_id.flower_analysis_json or {}).get("flowers") or []
        detected_names = {(flower.get("name") or "").strip() for flower in flowers if flower.get("name")}
        mapped_names = set(
            self.env["flower.calculator.mapping"]
            .search([("chatgpt_name", "in", list(detected_names))])
            .mapped("chatgpt_name")
        )
        return sorted(detected_names - mapped_names)

    def _compute_new_chatgpt_names(self):
        for wizard in self:
            wizard.new_chatgpt_names = "\n".join(wizard._get_new_flower_names()) or wizard.env._(
                "No new flower names to add."
            )

    def action_confirm(self):
        self.ensure_one()
        self.sale_order_id._sync_flower_mappings()
        return {
            "type": "ir.actions.act_window",
            "res_model": "flower.calculator.mapping",
            "view_mode": "list,form",
            "name": self.env._("Flower Name Mapping"),
        }
