import json
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.ai.utils.llm_api_service import LLMApiService


class TestMappingAIProductMatch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        flower_category = cls.env["product.category"].search(
            [("complete_name", "=", "All / Lisi Grün / Urproduktion / Blumen")],
            limit=1,
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Rose Red Naomi",
                "sale_ok": True,
                "categ_id": flower_category.id or cls.env.ref("product.product_category_all").id,
            }
        )
        cls.mapping = cls.env["flower.calculator.mapping"].create(
            {
                "chatgpt_name": "Red rose",
                "german_name": "Rote Rose",
                "variety": "Red Naomi",
            }
        )

    @patch.object(LLMApiService, "request_llm")
    def test_ai_assigns_returned_catalog_product(self, request_llm):
        request_llm.return_value = [json.dumps({"product_id": self.product.id, "reason": "Matching variety"})]

        self.mapping.action_ai_find_product()

        self.assertEqual(self.mapping.product_id, self.product)
        user_prompt = request_llm.call_args.kwargs["user_prompts"][0]
        self.assertIn("Rote Rose", user_prompt)
        self.assertIn("Red Naomi", user_prompt)
        self.assertIn(f"{self.product.id}: {self.product.display_name}", user_prompt)

    @patch.object(LLMApiService, "request_llm")
    def test_ai_rejects_product_id_outside_catalog(self, request_llm):
        self.mapping.product_id = self.product
        request_llm.return_value = [json.dumps({"product_id": 999999999, "reason": "No match"})]

        self.mapping.action_ai_find_product()

        self.assertFalse(self.mapping.product_id)
