from odoo import fields, models


class FlowerCalculatorFlower(models.Model):
    _name = "flower.calculator.flower"
    _description = "Detected Flower"

    sale_order_id = fields.Many2one("sale.order", required=True, ondelete="cascade")
    name = fields.Char(required=True)
    quantity = fields.Float()
    size = fields.Selection([("small", "Small"), ("large", "Large")])
    product_id = fields.Many2one("product.product")
    description = fields.Text()
    genus = fields.Char()
    german_name = fields.Char()
    group_type = fields.Char()
    variety = fields.Char()
    color = fields.Char()
