_CAMPING_WEBSITE_DOMAIN = "https://camping.unternhub.at"
_CAMPING_STEP_HREF = "/shop/camping"
_PITCH_STEP_HREF = "/shop/pitch"
_DOG_PRODUCT_NAME = "Hunde"
_DOG_PRODUCT_XMLID = "product_dog"
_ADDITIONAL_GUEST_PRODUCT_NAME = "Zusätzliche Personen im Zelt"
_ADDITIONAL_GUEST_PRODUCT_XMLID = "product_additional_guest"
_ACCOMMODATION_PRODUCT_NAMES = [
    "Stellplatz Van (2P)",
    "Stellplatz Wohnwaagen (2P)",
    "Zeltplatz (2P)",
]
_LOCAL_TAX_PRODUCT_NAME = "City Tax"
_ELECTRICITY_PRODUCT_TEMPLATE_ID = 2898
_EXTRA_VEHICLE_PRODUCT_NAME = "Zusätzliches Fahrzeug"
_EXTRA_VEHICLE_PRODUCT_XMLID = "product_extra_vehicle"
# The "Pro Nacht" (nightly) UoM the other per-stay fee products (Hunde, ...)
# already use has no stable xmlid of its own (unlike the recurrence below,
# which does) - same kind of hardcoded reference as _ELECTRICITY_PRODUCT_TEMPLATE_ID.
_NIGHT_UOM_ID = 66


def post_init_hook(env):
    _setup_camping_step(env)
    _setup_pitch_step(env)
    _setup_dog_product(env)
    _reorder_cart_step(env)
    _reorder_address_step(env)
    _setup_additional_guest_product(env)
    _setup_local_tax_product(env)
    _setup_electricity_product(env)
    _setup_extra_vehicle_product(env)


def _setup_camping_step(env):
    website = env["website"].search([("domain", "=", _CAMPING_WEBSITE_DOMAIN)], limit=1)
    if not website:
        return

    step = env["website.checkout.step"].search(
        [
            ("website_id", "=", website.id),
            ("step_href", "=", _CAMPING_STEP_HREF),
        ],
        limit=1,
    )
    if step:
        return

    checkout_step = env["website.checkout.step"].search(
        [
            ("website_id", "=", website.id),
            ("step_href", "=", "/shop/checkout"),
        ],
        limit=1,
    )

    env["website.checkout.step"].create(
        {
            "website_id": website.id,
            "name": "Camping",
            "sequence": (checkout_step.sequence or 250) + 10,
            "step_href": _CAMPING_STEP_HREF,
            "main_button_label": "Continue",
            "back_button_label": "Back to camping info",
            "is_published": True,
        }
    )


def _setup_pitch_step(env):
    website = env["website"].search([("domain", "=", _CAMPING_WEBSITE_DOMAIN)], limit=1)
    if not website:
        return

    step = env["website.checkout.step"].search(
        [("website_id", "=", website.id), ("step_href", "=", _PITCH_STEP_HREF)],
        limit=1,
    )
    if step:
        return

    camping_step = env["website.checkout.step"].search(
        [("website_id", "=", website.id), ("step_href", "=", _CAMPING_STEP_HREF)],
        limit=1,
    )
    env["website.checkout.step"].create(
        {
            "website_id": website.id,
            "name": "Pitch",
            "sequence": (camping_step.sequence or 260) + 10,
            "step_href": _PITCH_STEP_HREF,
            "main_button_label": "Continue",
            "back_button_label": "Back to pitch selection",
            "is_published": True,
        }
    )


def _reorder_cart_step(env):
    website = env["website"].search([("domain", "=", _CAMPING_WEBSITE_DOMAIN)], limit=1)
    if not website:
        return

    camping_step = env["website.checkout.step"].search(
        [
            ("website_id", "=", website.id),
            ("step_href", "=", _CAMPING_STEP_HREF),
        ],
        limit=1,
    )
    cart_step = env["website.checkout.step"].search(
        [
            ("website_id", "=", website.id),
            ("step_href", "=", "/shop/cart"),
        ],
        limit=1,
    )
    if not camping_step or not cart_step:
        return

    pitch_step = env["website.checkout.step"].search(
        [("website_id", "=", website.id), ("step_href", "=", _PITCH_STEP_HREF)],
        limit=1,
    )
    target_sequence = (pitch_step or camping_step).sequence + 10
    if cart_step.sequence != target_sequence:
        cart_step.sequence = target_sequence


def _reorder_address_step(env):
    website = env["website"].search([("domain", "=", _CAMPING_WEBSITE_DOMAIN)], limit=1)
    if not website:
        return

    address_step = env["website.checkout.step"].search(
        [
            ("website_id", "=", website.id),
            ("step_href", "=", "/shop/checkout"),
        ],
        limit=1,
    )
    cart_step = env["website.checkout.step"].search(
        [
            ("website_id", "=", website.id),
            ("step_href", "=", "/shop/cart"),
        ],
        limit=1,
    )
    if not address_step or not cart_step:
        return

    target_sequence = cart_step.sequence + 10
    if address_step.sequence != target_sequence:
        address_step.sequence = target_sequence


def _setup_dog_product(env):
    existing = env["ir.model.data"].search(
        [
            ("module", "=", "camping_checkout"),
            ("name", "=", _DOG_PRODUCT_XMLID),
        ],
        limit=1,
    )
    if existing:
        return

    product = env["product.product"].search([("name", "=", _DOG_PRODUCT_NAME)], limit=1)
    if not product:
        return

    env["ir.model.data"].create(
        {
            "module": "camping_checkout",
            "name": _DOG_PRODUCT_XMLID,
            "model": "product.product",
            "res_id": product.id,
            "noupdate": True,
        }
    )


def _setup_additional_guest_product(env):
    existing = env["ir.model.data"].search(
        [
            ("module", "=", "camping_checkout"),
            ("name", "=", _ADDITIONAL_GUEST_PRODUCT_XMLID),
        ],
        limit=1,
    )
    if not existing:
        product = env["product.product"].search([("name", "=", _ADDITIONAL_GUEST_PRODUCT_NAME)], limit=1)
        if not product:
            return
        env["ir.model.data"].create(
            {
                "module": "camping_checkout",
                "name": _ADDITIONAL_GUEST_PRODUCT_XMLID,
                "model": "product.product",
                "res_id": product.id,
                "noupdate": True,
            }
        )
        existing = env["ir.model.data"].search(
            [
                ("module", "=", "camping_checkout"),
                ("name", "=", _ADDITIONAL_GUEST_PRODUCT_XMLID),
            ],
            limit=1,
        )

    extra_product = env["product.product"].browse(existing.res_id)
    accommodation_templates = env["product.template"].search([("name", "in", _ACCOMMODATION_PRODUCT_NAMES)])
    accommodation_templates.filtered(lambda t: not t.x_additional_guest_product_id).write(
        {"x_additional_guest_product_id": extra_product.id}
    )


def _setup_local_tax_product(env):
    website = env["website"].search([("domain", "=", _CAMPING_WEBSITE_DOMAIN)], limit=1)
    if not website or not website.company_id or website.company_id.x_local_tax_product_id:
        return

    product = env["product.product"].search([("name", "=", _LOCAL_TAX_PRODUCT_NAME)], limit=1)
    if not product:
        return

    website.company_id.x_local_tax_product_id = product.id


def _setup_electricity_product(env):
    electricity_product = (
        env["product.template"].browse(_ELECTRICITY_PRODUCT_TEMPLATE_ID).exists().product_variant_id
    )
    if not electricity_product:
        return

    accommodation_templates = env["product.template"].search([("name", "in", _ACCOMMODATION_PRODUCT_NAMES)])
    accommodation_templates.filtered(lambda t: not t.x_electricity_product_id).write(
        {"x_electricity_product_id": electricity_product.id}
    )


def _setup_extra_vehicle_product(env):
    """Create the per-night "extra vehicle" fee product, unlike the other fee
    products above this one isn't expected to already exist - it's created
    here so it has a real price to be set on it afterward in the backend.
    """
    existing = env["ir.model.data"].search(
        [("module", "=", "camping_checkout"), ("name", "=", _EXTRA_VEHICLE_PRODUCT_XMLID)],
        limit=1,
    )
    if existing:
        return

    night_uom = env["uom.uom"].browse(_NIGHT_UOM_ID).exists()
    recurrence = env.ref("sale_renting.recurrence_nightly", raise_if_not_found=False)
    if not night_uom or not recurrence:
        return

    product = env["product.product"].create(
        {
            "name": _EXTRA_VEHICLE_PRODUCT_NAME,
            "type": "service",
            "rent_ok": True,
            "sale_ok": False,
            "invoice_policy": "order",
            "uom_id": night_uom.id,
            "list_price": 0.0,
        }
    )
    env["product.pricing"].create(
        {
            "product_template_id": product.product_tmpl_id.id,
            "recurrence_id": recurrence.id,
            "price": 0.0,
        }
    )
    env["ir.model.data"].create(
        {
            "module": "camping_checkout",
            "name": _EXTRA_VEHICLE_PRODUCT_XMLID,
            "model": "product.product",
            "res_id": product.id,
            "noupdate": True,
        }
    )
