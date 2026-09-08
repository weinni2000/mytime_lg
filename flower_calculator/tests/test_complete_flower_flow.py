from odoo.tests.common import TransactionCase


class TestCompleteFlowerFlow(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        partner = cls.env["res.partner"].create({"name": "Complete Flower Flow Customer"})
        cls.order = cls.env["sale.order"].create({"partner_id": partner.id})
        cls.order.company_id.default_flower_small = 0.75
        cls.order.company_id.default_flower_large = 2.50

    def test_unknown_flowers_get_mappings_and_sized_fallback_lines(self):
        self.order.flower_analysis_json = {
            "flowers": [
                {
                    "name": "Uncatalogued Small Flower",
                    "quantity": 4,
                    "size": "small",
                    "product_id": None,
                    "german_name": "Kleine Testblume",
                    "variety": "Mini",
                },
                {
                    "name": "Uncatalogued Large Flower",
                    "quantity": 2,
                    "size": "large",
                    "product_id": None,
                    "german_name": "Große Testblume",
                    "variety": "Maxi",
                },
            ]
        }

        mappings = self.order._sync_flower_mappings()
        self.order.action_add_flowers_to_order_lines()

        self.assertEqual(len(mappings), 2)
        self.assertFalse(mappings.mapped("product_id"))
        small_mapping = mappings.filtered(lambda mapping: mapping.chatgpt_name == "Uncatalogued Small Flower")
        self.assertEqual(small_mapping.german_name, "Kleine Testblume")
        self.assertEqual(small_mapping.variety, "Mini")

        small_line = self.order.order_line.filtered(lambda line: line.name == "Uncatalogued Small Flower")
        large_line = self.order.order_line.filtered(lambda line: line.name == "Uncatalogued Large Flower")
        self.assertEqual(small_line.product_uom_qty, 4)
        self.assertEqual(small_line.price_unit, 0.75)
        self.assertEqual(small_line.price_subtotal, 3.0)
        self.assertEqual(large_line.product_uom_qty, 2)
        self.assertEqual(large_line.price_unit, 2.50)
        self.assertEqual(large_line.price_subtotal, 5.0)
        self.assertTrue((small_line | large_line).mapped("flower_calculator_generated"))

    def test_recreating_flow_replaces_only_generated_lines(self):
        manual_line = self.env["sale.order.line"].create(
            {
                "order_id": self.order.id,
                "name": "Manual service",
                "product_uom_qty": 1,
                "price_unit": 10,
            }
        )
        self.order.flower_analysis_json = {
            "flowers": [
                {
                    "name": "Replaceable Flower",
                    "quantity": 1,
                    "size": "small",
                    "product_id": None,
                }
            ]
        }

        self.order.action_add_flowers_to_order_lines()
        first_generated_line = self.order.order_line.filtered("flower_calculator_generated")
        self.order.action_add_flowers_to_order_lines()

        self.assertIn(manual_line, self.order.order_line)
        self.assertNotIn(first_generated_line, self.order.order_line)
        self.assertEqual(len(self.order.order_line.filtered("flower_calculator_generated")), 1)
