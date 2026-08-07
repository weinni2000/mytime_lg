from odoo import fields, models


class IrCronTag(models.Model):
    _name = "ir.cron.tag"
    _description = "Scheduled Action Tag"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    color = fields.Integer()

    _name_uniq = models.Constraint("unique(name)", "A scheduled action tag with this name already exists.")


class IrCron(models.Model):
    _inherit = "ir.cron"

    tag_ids = fields.Many2many("ir.cron.tag", string="Tags")
