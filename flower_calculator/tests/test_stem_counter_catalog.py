from odoo.tests.common import TransactionCase


class TestStemCounterCatalog(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        flower_category = cls.env["product.category"].search(
            [("complete_name", "=", "All / Lisi Grün / Urproduktion / Blumen")],
            limit=1,
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Catalog Rose",
                "sale_ok": True,
                "categ_id": flower_category.id or cls.env.ref("product.product_category_all").id,
            }
        )
        partner = cls.env["res.partner"].create({"name": "Stem Counter Customer"})
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "flower_counter": "stems",
            }
        )

    def test_stem_mode_sends_product_catalog_to_model(self):
        prompts = self.order._get_flower_analysis_system_prompts()

        self.assertIn("STEMS", prompts[0])
        self.assertIn(f"{self.product.id}: {self.product.display_name}", "\n".join(prompts))
        self.assertIn("set product_id", prompts[0])

    def test_stem_mode_keeps_only_catalog_product_ids(self):
        analysis = {
            "flowers": [
                {
                    "name": "Catalog Rose",
                    "product_id": self.product.id,
                    "description": "A red, single-headed rose stem",
                },
                {
                    "name": "Unknown Wildflower",
                    "product_id": 999999999,
                    "description": "Small blue flowers on a branching stem",
                    "genus": "Unknown",
                },
            ]
        }

        self.order._validate_analysis_product_ids(analysis)

        self.assertEqual(analysis["flowers"][0]["product_id"], self.product.id)
        self.assertIsNone(analysis["flowers"][1]["product_id"])
        self.assertEqual(
            analysis["flowers"][1]["description"],
            "Small blue flowers on a branching stem",
        )
        self.assertEqual(analysis["flowers"][1]["genus"], "Unknown")
