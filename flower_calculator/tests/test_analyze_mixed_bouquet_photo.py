import base64
from pathlib import Path

from odoo.tests.common import TransactionCase, tagged

_IMAGE_PATH = Path(__file__).parents[1] / "misc" / "img" / "fd763b69-3b14-493e-84a7-b6bc94bde379.jpg"


@tagged("ai_external", "-standard", "post_install", "-at_install")
class TestAnalyzeMixedBouquetPhoto(TransactionCase):
    def test_reports_flowers_not_in_catalog(self):
        """This bouquet mixes wildflowers/grasses with typical cut flowers, so it is
        expected to contain at least one flower with no catalog match. ChatGPT must still
        report its name and quantity instead of silently dropping it."""
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

        for flower in flowers:
            self.assertTrue((flower.get("name") or "").strip(), f"Flower is missing a name: {flower!r}")
            self.assertTrue(flower.get("quantity"), f"Flower is missing a quantity: {flower!r}")

        unmatched_flowers = [flower for flower in flowers if not flower.get("product_id")]
        self.assertTrue(
            unmatched_flowers,
            "Expected at least one flower with no catalog match (name/quantity still reported), "
            f"but every flower had a product_id: {flowers!r}",
        )
