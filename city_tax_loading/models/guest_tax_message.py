from odoo import fields, models


class GuestTaxMessage(models.Model):
    _inherit = "guest.tax.message"

    x_import_key = fields.Char(
        string="Import Key",
        copy=False,
        index=True,
        help="Internal deduplication key (email + check-in date) for guests "
        "imported from a Google Sheet, so re-loading the same month is safe.",
    )
    x_sheet_id = fields.Many2one("guest.tax.sheet", string="Source Sheet", copy=False, readonly=True)
