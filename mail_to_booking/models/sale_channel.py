from odoo import fields, models


class SaleChannel(models.Model):
    _inherit = "sale.channel"

    email = fields.Char()
    synonyms = fields.Text(
        help="Alternative names used to identify this sales channel. Enter one name per line.",
    )
    force_single_product = fields.Boolean(
        string="Immer Standardprodukt verwenden",
        help="Überspringt die produkt_hint-Zuordnungstabelle und verwendet für "
        "jede Buchung dieses Kanals immer das Standardprodukt.",
    )
    default_product_id = fields.Many2one(
        "product.product",
        string="Standardprodukt",
        help="Wird nur verwendet, wenn 'Immer Standardprodukt verwenden' aktiviert ist.",
    )
