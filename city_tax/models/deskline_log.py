from odoo import fields, models


class DesklineLog(models.Model):
    _name = "deskline.log"
    _description = "Deskline API Log"
    _order = "id desc"

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    success = fields.Boolean()
    request_url = fields.Char()
    request_body = fields.Text()
    response_status = fields.Integer()
    response_body = fields.Text()
