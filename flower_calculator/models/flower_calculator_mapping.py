import json

from odoo import fields, models
from odoo.exceptions import UserError

from odoo.addons.ai.utils.llm_api_service import LLMApiService

from ._const import (
    FLOWER_CALCULATOR_MODEL,
    FLOWER_MODEL_PROVIDERS,
    FLOWER_PRODUCT_CATEGORY_COMPLETE_NAME,
)

_AI_PRODUCT_MATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "product_id": {"type": ["integer", "null"]},
        "reason": {"type": "string"},
    },
    "required": ["product_id", "reason"],
    "additionalProperties": False,
}


class FlowerCalculatorMapping(models.Model):
    _name = "flower.calculator.mapping"
    _description = "Flower Calculator Name Mapping"

    chatgpt_name = fields.Char(required=True)
    german_name = fields.Char()
    variety = fields.Char()
    product_id = fields.Many2one("product.product")

    _chatgpt_name_uniq = models.Constraint(
        "UNIQUE(chatgpt_name)",
        "This ChatGPT flower name is already mapped.",
    )

    def _get_flower_products(self):
        domain = [("sale_ok", "=", True)]
        category = self.env["product.category"].search(
            [("complete_name", "=", FLOWER_PRODUCT_CATEGORY_COMPLETE_NAME)],
            limit=1,
        )
        if category:
            domain.append(("categ_id", "child_of", category.id))
        return self.env["product.product"].search(domain)

    def action_ai_find_product(self):
        self.ensure_one()
        products = self._get_flower_products()
        if not products:
            raise UserError(self.env._("There are no saleable flower products to search."))

        catalog = "; ".join(f"{product.id}: {product.display_name}" for product in products)
        flower_details = ", ".join(
            value
            for value in (
                self.chatgpt_name,
                self.german_name,
                self.variety,
            )
            if value
        )
        system_prompt = (
            "You match a detected flower to a product catalog. Choose the single best fitting "
            "product using the flower name, German name, and variety. Return only an ID from the "
            "provided catalog. Return null when no product is a sufficiently good match; never "
            "invent an ID."
        )
        user_prompt = f"Detected flower: {flower_details}\nProduct catalog (id: name): {catalog}"
        provider = FLOWER_MODEL_PROVIDERS.get(FLOWER_CALCULATOR_MODEL, "openai")
        responses = LLMApiService(self.env, provider=provider).request_llm(
            llm_model=FLOWER_CALCULATOR_MODEL,
            system_prompts=[system_prompt],
            user_prompts=[user_prompt],
            schema=_AI_PRODUCT_MATCH_SCHEMA,
            temperature=0,
        )
        if not responses:
            raise UserError(self.env._("AI did not return a product match."))
        try:
            result = json.loads(responses[0])
        except (TypeError, ValueError) as error:
            raise UserError(self.env._("AI did not return a valid product match.")) from error

        matched_product = products.filtered(lambda product: product.id == result.get("product_id"))
        self.product_id = matched_product[:1]
        if self.product_id:
            title = self.env._("Product matched")
            message = self.env._("AI selected %(product)s") % {"product": self.product_id.display_name}
            notification_type = "success"
        else:
            title = self.env._("No product match")
            message = result.get("reason") or self.env._("AI could not find a suitable catalog product.")
            notification_type = "warning"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notification_type,
                "sticky": False,
            },
        }
