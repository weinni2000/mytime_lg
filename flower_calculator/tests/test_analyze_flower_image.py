import base64
from pathlib import Path

from odoo.tests.common import TransactionCase, tagged

_IMAGE_PATH = Path(__file__).parents[1] / "misc" / "img" / "7aa478f0-e862-4918-8d68-563037943e78.jpg"
_EXPECTED_PRODUCT_NAME = "Bio-Lilie (Rosellas Dream)"


@tagged("ai_external", "-standard", "post_install", "-at_install")
class TestAnalyzeFlowerImage(TransactionCase):
    def test_analyzes_bio_lilie_photo(self):
        expected_product = self.env["product.product"].search(
            [("display_name", "=", _EXPECTED_PRODUCT_NAME)], limit=1
        )
        if not expected_product:
            self.skipTest(f"Product {_EXPECTED_PRODUCT_NAME!r} not found in this database's catalog.")

        partner_id = self.env["res.partner"].create({"name": "Flower Calculator Test Customer"})
        order_id = self.env["sale.order"].create(
            {
                "partner_id": partner_id.id,
                "flower_image": base64.b64encode(_IMAGE_PATH.read_bytes()),
            }
        )
        order_id.action_analyze_flower_image()

        flowers = (order_id.flower_analysis_json or {}).get("flowers") or []
        self.assertTrue(flowers, "ChatGPT returned no flowers for the photo")

        matching_flowers = [flower for flower in flowers if flower.get("product_id") == expected_product.id]
        self.assertTrue(
            matching_flowers,
            f"Expected a flower with product_id {expected_product.id} ({_EXPECTED_PRODUCT_NAME!r}), "
            f"got: {flowers!r}",
        )
