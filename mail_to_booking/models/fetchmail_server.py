from odoo import api, fields, models

MAIL_TO_BOOKING_MODEL = "mail.to.booking"


class FetchmailServer(models.Model):
    _inherit = "fetchmail.server"

    mail_to_booking_enabled = fields.Boolean(
        string="Buchungen per DeepSeek erkennen",
        help="Jede über diesen Server eingehende E-Mail wird an DeepSeek "
        "geschickt, um automatisch eine Buchung zu erkennen und anzulegen. "
        "'Neuen Datensatz anlegen' wird dabei automatisch auf 'Mail to Booking' gesetzt.",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        help="Buchungen aus E-Mails dieses Servers werden immer dieser Firma zugeordnet, "
        "unabhängig von der aktuell aktiven Firma des Cron-Jobs.",
    )
    available_sale_channel_ids = fields.Many2many(
        "sale.channel",
        compute="_compute_available_sale_channel_ids",
        string="Available Sales Channels",
    )
    allowed_product_ids = fields.Many2many(
        "product.product",
        string="Zulässige Produkte",
        domain=[("x_is_a_room_offer", "=", True)],
        help="Wird eine Buchung aus einer E-Mail dieses Servers erstellt, "
        "kommt nur eines dieser Produkte in Frage. Leer lassen, um alle "
        "verkaufs-/vermietbaren Produkte zuzulassen.",
    )
    notify_user_id = fields.Many2one(
        "res.users",
        string="Bei Warnung benachrichtigen",
        help="Dieser Benutzer erhält eine Nachricht, sobald eine aus einer "
        "E-Mail dieses Servers erstellte Mail-to-Booking-Buchung eine "
        "Warnung oder einen Fehler hat (kein Produkt gefunden, Buchung "
        "konnte nicht bestätigt werden, Extraktion fehlgeschlagen).",
    )

    @api.onchange("mail_to_booking_enabled")
    def _onchange_mail_to_booking_enabled(self):
        for record in self:
            record.object_id = record._mail_to_booking_model_id() if record.mail_to_booking_enabled else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("mail_to_booking_enabled"):
                vals["object_id"] = self._mail_to_booking_model_id().id
        return super().create(vals_list)

    def write(self, vals):
        if "mail_to_booking_enabled" in vals:
            vals["object_id"] = self._mail_to_booking_model_id().id if vals["mail_to_booking_enabled"] else False
        return super().write(vals)

    def _mail_to_booking_model_id(self):
        return self.env["ir.model"]._get(MAIL_TO_BOOKING_MODEL)

    def _compute_available_sale_channel_ids(self):
        channel_ids = self.env["sale.channel"].search([])  # pylint: disable=no-search-all
        for record in self:
            record.available_sale_channel_ids = channel_ids
