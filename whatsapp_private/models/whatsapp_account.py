from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WhatsAppAccount(models.Model):
    _inherit = "whatsapp.account"

    connection_type = fields.Selection(
        selection=[
            ("cloud", "Whatsapp Business Cloud API"), #Whatsapp Business Cloud API
            ("private", "Private WhatsApp"),
        ],
        string="Type",
        required=True,
        default="cloud",
        tracking=True,
    )
    is_private_whatsapp = fields.Boolean(
        compute="_compute_is_private_whatsapp",
    )

    # The upstream fields are globally required. Private Business accounts use
    # the linked-device session instead, so their requirement is conditional.
    app_uid = fields.Char(required=False)
    app_secret = fields.Char(required=False)
    account_uid = fields.Char(required=False)
    phone_uid = fields.Char(required=False)
    token = fields.Char(required=False)

    private_company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        help="Company whose private WhatsApp session is used by this account.",
    )
    private_qr_code = fields.Binary(
        related="private_company_id.whatsapp_private_qr_code",
        string="Private WhatsApp QR Code",
        readonly=True,
    )
    private_connection_status = fields.Char(
        related="private_company_id.whatsapp_private_status",
        string="Private Connection Status",
        readonly=True,
    )
    private_status_detail = fields.Text(
        related="private_company_id.whatsapp_private_status_detail",
        string="Private Connection Detail",
        readonly=True,
    )

    @api.depends("connection_type")
    def _compute_is_private_whatsapp(self):
        for account in self:
            account.is_private_whatsapp = account.connection_type == "private"

    @api.constrains("notify_user_ids", "connection_type")
    def _check_notify_user_ids(self):
        for account in self:
            if account.connection_type == "cloud" and not account.notify_user_ids:
                raise ValidationError(_("Users to notify is required"))

    @api.constrains(
        "connection_type",
        "app_uid",
        "app_secret",
        "account_uid",
        "phone_uid",
        "token",
        "private_company_id",
    )
    def _check_connection_credentials(self):
        cloud_fields = {
            "app_uid": _("App ID"),
            "app_secret": _("App Secret"),
            "account_uid": _("WhatsApp Business Account ID"),
            "phone_uid": _("Phone Number ID"),
            "token": _("Access Token"),
        }
        for account in self:
            if account.connection_type == "private":
                if not account.private_company_id:
                    raise ValidationError(_("A company is required for a Private Business account."))
                continue
            missing = [label for field_name, label in cloud_fields.items() if not account[field_name]]
            if missing:
                raise ValidationError(
                    _("The following Cloud API credentials are required: %s", ", ".join(missing))
                )

    def action_private_whatsapp_connect(self):
        self.ensure_one()
        if self.connection_type != "private":
            raise ValidationError(_("Set the account type to Private Business first."))
        self.private_company_id.action_whatsapp_private_connect()
        return self.action_private_whatsapp_refresh()

    def action_private_whatsapp_refresh(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("WhatsApp Business Account"),
            "res_model": "whatsapp.account",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_private_whatsapp_send_message(self):
        self.ensure_one()
        if self.connection_type != "private":
            raise ValidationError(_("This action is only available for Private Business accounts."))
        return self.private_company_id.action_whatsapp_private_open_send_wizard()
