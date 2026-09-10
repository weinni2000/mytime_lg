import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_EXTRA_VEHICLE_PRODUCT_NAME = "Zusätzliches Fahrzeug"
_EXTRA_VEHICLE_PRODUCT_XMLID = "product_extra_vehicle"
_NIGHT_UOM_ID = 66


def migrate(cr, version):
    """Create the extra-vehicle fee product for modules already installed
    before this version (post_init_hook only runs on a fresh install).

    Kept self-contained (not imported from hooks.py) like the other
    migration scripts in this module: migration scripts are loaded outside
    the normal package import machinery, so a relative import back into the
    module isn't reliable here.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    existing = env["ir.model.data"].search(
        [("module", "=", "camping_checkout"), ("name", "=", _EXTRA_VEHICLE_PRODUCT_XMLID)],
        limit=1,
    )
    if existing:
        return

    night_uom = env["uom.uom"].browse(_NIGHT_UOM_ID).exists()
    recurrence = env.ref("sale_renting.recurrence_nightly", raise_if_not_found=False)
    if not night_uom or not recurrence:
        _logger.warning("camping_checkout: could not create the extra-vehicle product (missing uom or recurrence)")
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
    _logger.info("camping_checkout: created the extra-vehicle fee product")
