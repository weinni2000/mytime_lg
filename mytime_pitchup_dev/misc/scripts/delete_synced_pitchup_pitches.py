#!/usr/bin/env python3
import argparse
import logging
import os
import sys
import xmlrpc.client
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR / ".env"
_logger = logging.getLogger(__name__)


def load_env(path):
    if not path.exists():
        raise RuntimeError(f"Missing env file: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def rpc_call(models, db, uid, password, model, method, *args, **kwargs):
    return models.execute_kw(db, uid, password, model, method, args, kwargs)


def ensure_model_exists(models, db, uid, password, model):
    model_ids = rpc_call(
        models,
        db,
        uid,
        password,
        "ir.model",
        "search",
        [("model", "=", model)],
        limit=1,
    )
    if not model_ids:
        raise RuntimeError(f"Model {model} does not exist on {db} at {os.environ['ODOO_URL']}.")


def main():
    parser = argparse.ArgumentParser(
        description="Delete synced Pitchup pitch mappings so they can be fetched and mapped again."
    )
    parser.add_argument(
        "--company-id",
        type=int,
        help="Only delete mappings for this company. Defaults to all companies.",
    )
    parser.add_argument(
        "--include-auto-products",
        action="store_true",
        help="Also delete auto-created product templates with default_code starting with PITCHUP-.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually delete records. Without this flag the script only logs a dry run.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    load_env(ENV_PATH)
    url = os.environ["ODOO_URL"].rstrip("/")
    db = os.environ["ODOO_DB"]
    username = os.environ["ODOO_USERNAME"]
    password = os.environ["ODOO_API_KEY"]

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise RuntimeError("Odoo authentication failed.")

    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    ensure_model_exists(models, db, uid, password, "pitchup.product.mapping")

    mapping_domain = []
    if args.company_id:
        mapping_domain.append(("company_id", "=", args.company_id))
    mapping_ids = rpc_call(
        models,
        db,
        uid,
        password,
        "pitchup.product.mapping",
        "search",
        mapping_domain,
    )
    mappings = rpc_call(
        models,
        db,
        uid,
        password,
        "pitchup.product.mapping",
        "read",
        mapping_ids,
        fields=["pitch_type_id", "pitch_type_name", "product_template_id", "company_id"],
    )

    _logger.info("Pitchup mappings to delete: %s", len(mapping_ids))
    for mapping in mappings:
        company = mapping["company_id"][1] if mapping.get("company_id") else ""
        product_template = mapping["product_template_id"][1] if mapping.get("product_template_id") else ""
        pitch_type = mapping["pitch_type_id"]
        name = mapping.get("pitch_type_name") or ""
        _logger.info("- %s %s -> %s (%s)", pitch_type, name, product_template, company)

    product_template_ids = []
    if args.include_auto_products:
        product_template_ids = rpc_call(
            models,
            db,
            uid,
            password,
            "product.template",
            "search",
            [("default_code", "=like", "PITCHUP-%")],
        )
        product_templates = rpc_call(
            models,
            db,
            uid,
            password,
            "product.template",
            "read",
            product_template_ids,
            fields=["display_name", "default_code"],
        )
        _logger.info(
            "Auto-created PITCHUP-* product templates to delete: %s",
            len(product_template_ids),
        )
        for product_template in product_templates:
            _logger.info(
                "- %s %s",
                product_template["default_code"],
                product_template["display_name"],
            )

    if not args.confirm:
        _logger.info("Dry run only. Re-run with --confirm to delete.")
        return 0

    if mapping_ids:
        rpc_call(
            models,
            db,
            uid,
            password,
            "pitchup.product.mapping",
            "unlink",
            mapping_ids,
        )
    if product_template_ids:
        rpc_call(
            models,
            db,
            uid,
            password,
            "product.template",
            "unlink",
            product_template_ids,
        )

    _logger.info("Cleanup complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
