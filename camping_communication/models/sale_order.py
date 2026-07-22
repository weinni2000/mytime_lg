from markupsafe import Markup

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import plaintext2html


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_send_camping_confirmation_email(self):
        template_id = self.env.ref(
            "camping_communication.mail_template_camping_confirmation",
            raise_if_not_found=False,
        )
        if not template_id:
            raise UserError(_("The camping confirmation email template is missing."))

        for order_id in self:
            if not order_id.partner_id.email:
                raise UserError(
                    _(
                        "The customer %(partner)s has no email address.",
                        partner=order_id.partner_id.display_name,
                    )
                )
            if not order_id._get_camping_confirmation_product_texts():
                raise UserError(
                    _(
                        "No camping confirmation text is configured on any product of %(order)s.",
                        order=order_id.display_name,
                    )
                )
            template_id.send_mail(order_id.id, force_send=True, raise_exception=True)

        return True

    def _get_camping_confirmation_product_texts(self):
        self.ensure_one()
        product_text_by_template_id = {}
        order_line_ids = self.order_line.filtered(lambda sale_line_id: not sale_line_id.display_type)
        for line_id in order_line_ids:
            product_template_id = line_id.product_id.product_tmpl_id
            text = product_template_id.camping_confirmation_text
            if text and product_template_id.id not in product_text_by_template_id:
                product_text_by_template_id[product_template_id.id] = text.strip()
        return [text for text in product_text_by_template_id.values() if text]

    def _get_camping_confirmation_body_html(self):
        self.ensure_one()
        body_parts = [plaintext2html(text) for text in self._get_camping_confirmation_product_texts()]
        return Markup("<br/>").join(Markup(body_part) for body_part in body_parts)

    def _get_camping_confirmation_subject(self):
        self.ensure_one()
        company_name = self.company_id.name or self.env.company.name
        return _(
            "%(company)s camping confirmation for %(order)s",
            company=company_name,
            order=self.name,
        )
