import base64
from datetime import date

from odoo.http import request, route

from odoo.addons.website_sale.controllers.cart import Cart
from odoo.addons.website_sale.controllers.main import WebsiteSale

CAMPING_STEP_HREF = "/shop/camping"
DOG_SPECIES_XMLID = "animal.dog"
DOG_PRODUCT_XMLID = "camping_checkout.product_dog"
ADDITIONAL_GUEST_PRODUCT_XMLID = "camping_checkout.product_additional_guest"
LOCAL_TAX_MIN_AGE = 16


class WebsiteSaleCampingCheckout(WebsiteSale):
    def _parse_form_data(self, form_data):
        id_document_front = form_data.pop("x_id_document_front", None)
        address_values, extra_form_data = super()._parse_form_data(form_data)

        if id_document_front and getattr(id_document_front, "filename", ""):
            address_values["x_id_document_front"] = base64.b64encode(id_document_front.read())

        return address_values, extra_form_data

    def _prepare_address_form_values(self, *args, **kwargs):
        rendering_values = super()._prepare_address_form_values(*args, **kwargs)
        countries = rendering_values.get("countries")
        if countries is not None:
            priority_countries = countries.filtered(lambda c: c.x_checkout_priority_sequence).sorted(
                key=lambda c: c.x_checkout_priority_sequence
            )
            rendering_values["priority_countries"] = priority_countries
            rendering_values["countries"] = countries - priority_countries
        return rendering_values

    # === CHECKOUT FLOW - CAMPING STEP METHODS === #

    @route([CAMPING_STEP_HREF], type="http", auth="public", website=True, sitemap=False)
    def shop_camping(self, **post):
        order_sudo = request.cart
        redirection = self._check_cart(order_sudo)
        if redirection:
            return redirection

        sudo_env = request.env(su=True)
        dog_species = sudo_env.ref(DOG_SPECIES_XMLID, raise_if_not_found=False)
        values = {
            "website_sale_order": order_sudo,
            "order": order_sudo,
            "vehicle": order_sudo.vehicle_ids[:1],
            "vehicle_categories": request.env["camping.vehicle.type"].sudo().search([]),
            "dogs": order_sudo.animal_ids,
            "with_electricity": self._has_camping_electricity(order_sudo),
            "dog_breeds": sudo_env["animal.breed"].search(
                [("species_id", "=", dog_species.id)] if dog_species else []
            ),
            "guest_rows": self._get_camping_guest_rows(order_sudo),
        }
        values.update(request.website._get_checkout_step_values())

        return request.render("camping_checkout.camping_step", values)

    def _get_camping_guest_rows(self, order_sudo):
        main_guest_line = order_sudo.x_guest_line_ids.filtered(lambda g: g.x_main_guest)[:1]
        companion_lines = order_sudo.x_guest_line_ids.filtered(lambda g: not g.x_main_guest)

        main_row = {
            "name": main_guest_line.x_guest_name if main_guest_line else order_sudo.partner_id.name,
            "age": main_guest_line.x_guest_age if main_guest_line else order_sudo.partner_id.x_age,
        }
        rows = [main_row] + [{"name": g.x_guest_name, "age": g.x_guest_age} for g in companion_lines]
        return rows

    @route(
        [f"{CAMPING_STEP_HREF}/submit"],
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        sitemap=False,
    )
    def shop_camping_submit(self, **post):
        order_sudo = request.cart
        redirection = self._check_cart(order_sudo)
        if redirection:
            return redirection

        category_id = post.get("x_vehicle_category_id")
        if category_id:
            vehicle_vals = {
                "license_plate": (post.get("x_vehicle_license_plate") or "").strip(),
                "category_id": int(category_id),
            }
            vehicle_sudo = order_sudo.vehicle_ids[:1]
            if vehicle_sudo:
                vehicle_sudo.write(vehicle_vals)
            else:
                request.env["camping.fleet.vehicle"].sudo().create(
                    {
                        **vehicle_vals,
                        "sale_order_id": order_sudo.id,
                    }
                )

        self._update_camping_dogs(order_sudo, post)
        self._update_electricity_product(order_sudo, post.get("x_with_electricity") == "on")
        guest_count, adult_guest_count = self._update_camping_guests(order_sudo)
        self._update_additional_guest_product(order_sudo, guest_count)
        self._update_local_tax_product(order_sudo, adult_guest_count)

        current_step = request.website._get_checkout_step(CAMPING_STEP_HREF)
        next_step = current_step._get_next_checkout_step(request.website._get_allowed_steps_domain())
        return request.redirect(next_step.step_href or "/shop/payment")

    def _update_camping_dogs(self, order_sudo, post):
        with_dogs = post.get("x_with_dogs") == "on"
        breed_ids = []
        if with_dogs:
            for breed_id in request.httprequest.form.getlist("x_dog_breed_id"):
                if breed_id.isdigit():
                    breed_ids.append(int(breed_id))

        order_sudo.animal_ids.sudo().unlink()

        sudo_env = request.env(su=True)
        dog_product = sudo_env.ref(DOG_PRODUCT_XMLID, raise_if_not_found=False)
        breeds = sudo_env["animal.breed"].browse(breed_ids).exists()
        if breeds:
            request.env["animal"].sudo().create(
                [
                    {
                        "name": "Dog",
                        "species_id": breed.species_id.id,
                        "breed_id": breed.id,
                        "product_id": dog_product.id if dog_product else False,
                        "sale_order_id": order_sudo.id,
                    }
                    for breed in breeds
                ]
            )

        if dog_product:
            self._set_camping_product_quantity(order_sudo, dog_product, len(breeds))

    def _set_camping_product_quantity(self, order_sudo, product, quantity):
        existing_line = order_sudo._cart_find_product_line(product.id, uom_id=product.uom_id.id)[:1]
        if existing_line:
            order_sudo._cart_update_line_quantity(line_id=existing_line.id, quantity=quantity)
        elif quantity > 0:
            order_sudo._cart_add(
                product_id=product.id,
                quantity=quantity,
                start_date=order_sudo.rental_start_date,
                end_date=order_sudo.rental_return_date,
            )

    @staticmethod
    def _get_camping_electricity_product(order_sudo):
        accommodation_lines = order_sudo.order_line.filtered(
            lambda line: line.product_id.product_tmpl_id.x_electricity_product_id
        )
        return accommodation_lines.product_id.product_tmpl_id.x_electricity_product_id[:1]

    def _has_camping_electricity(self, order_sudo):
        electricity_product = self._get_camping_electricity_product(order_sudo)
        return bool(
            electricity_product
            and order_sudo._cart_find_product_line(electricity_product.id, uom_id=electricity_product.uom_id.id)
        )

    def _update_electricity_product(self, order_sudo, selected):
        electricity_product = self._get_camping_electricity_product(order_sudo)
        if electricity_product:
            self._set_camping_product_quantity(order_sudo, electricity_product, int(selected))

    def _update_camping_guests(self, order_sudo):
        """Save the submitted guest rows and return (total_guests, adult_guests).

        The first row always represents the ordering customer: it's only ever
        used to make sure a main guest line exists, never to rename/edit the
        actual billing contact. Remaining rows are saved as companion guests.
        Age is required on every row, so every counted guest has a known age.
        """
        names = request.httprequest.form.getlist("x_guest_name")
        ages = request.httprequest.form.getlist("x_guest_age")

        sudo_env = request.env(su=True)
        main_guest_line = order_sudo.x_guest_line_ids.filtered(lambda g: g.x_main_guest)
        if not main_guest_line and order_sudo.partner_id:
            sudo_env["x_guests_line"].create(
                {
                    "x_sale_order_id": order_sudo.id,
                    "x_guest_partner_id": order_sudo.partner_id.id,
                    "x_main_guest": True,
                }
            )

        guest_ages = []
        if ages and ages[0].isdigit():
            guest_ages.append(int(ages[0]))

        guest_vals = []
        for name, age in zip(names[1:], ages[1:], strict=False):
            name = (name or "").strip()
            if not name:
                continue
            vals = {"name": name}
            if age.isdigit():
                age_int = int(age)
                vals["birthdate_date"] = self._birthdate_from_age(age_int)
                guest_ages.append(age_int)
            guest_vals.append(vals)

        order_sudo.x_guest_line_ids.filtered(lambda g: not g.x_main_guest).sudo().unlink()

        for vals in guest_vals:
            partner = sudo_env["res.partner"].create(vals)
            sudo_env["x_guests_line"].create(
                {
                    "x_sale_order_id": order_sudo.id,
                    "x_guest_partner_id": partner.id,
                    "x_main_guest": False,
                }
            )

        total_guests = 1 + len(guest_vals)
        adult_guests = sum(1 for age in guest_ages if age >= LOCAL_TAX_MIN_AGE)
        return total_guests, adult_guests

    def _update_additional_guest_product(self, order_sudo, guest_count):
        sudo_env = request.env(su=True)
        extra_product = sudo_env.ref(ADDITIONAL_GUEST_PRODUCT_XMLID, raise_if_not_found=False)
        if not extra_product:
            return

        accommodation_lines = order_sudo.order_line.filtered(
            lambda line: line.product_id.product_tmpl_id.x_additional_guest_product_id
        )
        if not accommodation_lines:
            return

        max_guest_total = sum(line.product_uom_qty * line.product_id.x_max_guest for line in accommodation_lines)
        extra_qty = max(guest_count - max_guest_total, 0)
        self._set_camping_product_quantity(order_sudo, extra_product, extra_qty)

    def _update_local_tax_product(self, order_sudo, adult_guest_count):
        tax_product = order_sudo.company_id.x_local_tax_product_id
        if not tax_product:
            return
        nights = 0
        if order_sudo.rental_start_date and order_sudo.rental_return_date:
            # Camping stays run evening check-in to morning check-out, e.g. 20:00 to
            # 07:00 the next day: barely 11 elapsed hours, but a full night's stay.
            # duration_days (raw elapsed time) would round that down to 0 nights, so
            # nights are counted by calendar date instead.
            nights = (order_sudo.rental_return_date.date() - order_sudo.rental_start_date.date()).days
        self._set_camping_product_quantity(order_sudo, tax_product, adult_guest_count * max(nights, 0))

    @staticmethod
    def _birthdate_from_age(age):
        today = date.today()
        try:
            return today.replace(year=today.year - age)
        except ValueError:
            # today is Feb 29 and the birth year isn't a leap year
            return today.replace(year=today.year - age, day=28)


class WebsiteSaleCampingCart(Cart):
    def cart(self, *args, **kwargs):
        # The "Address" step was moved before "Cart" (see hooks._reorder_cart_step), so a
        # customer who reaches /shop/cart via the header cart icon or the "View Cart" add-to-cart
        # notification before ever filling in an address should be sent there first.
        order_sudo = request.cart
        if order_sudo and order_sudo._is_anonymous_cart():
            return request.redirect("/shop/address")

        return super().cart(*args, **kwargs)
