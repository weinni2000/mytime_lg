from odoo import models
from odoo.http import request


class Website(models.Model):
    _inherit = "website"

    def _get_checkout_step_values(self):
        values = super()._get_checkout_step_values()

        order_sudo = request.cart
        next_step = values.get("next_website_checkout_step")
        if (
            order_sudo
            and values.get("current_website_checkout_step_href") == "/shop/cart"
            and next_step
            and next_step.step_href == "/shop/payment"
            and not order_sudo.vehicle_ids
        ):
            # The cart step was moved after "Camping" so it can show the added dog
            # product before payment, but it's still the very first page a customer
            # with an unfinished cart lands on: send them to the address step instead
            # of letting them skip straight to payment.
            address_step = self._get_checkout_step("/shop/checkout")
            if address_step:
                values["next_website_checkout_step"] = address_step
                values["next_website_checkout_step_href"] = address_step.step_href

        return values
