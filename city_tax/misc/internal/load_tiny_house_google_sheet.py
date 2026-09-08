# ruff: noqa: F821
# pylint: disable=print-used
"""Load all Tiny House guest registrations from the configured Google Sheet.

Run from the doodba19 directory:
    /home/weinni2000/venv_311_19/bin/python3 odoo/custom/src/odoo/odoo-bin shell \
        -c odoo_enterprise_prod.conf -d lisigruen.at \
        < odoo/custom/src/mytime_lg/city_tax/misc/internal/load_tiny_house_google_sheet.py

`env` is injected by `odoo-bin shell`, hence the F821/print-used suppressions above.
"""

from odoo.exceptions import UserError

SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/" "1fTuweviLcq9-xWBHwHLUu8iCrI6DfVBBa63gKg17gOM/edit?gid=1105064919"
)
SPREADSHEET_ID = "1fTuweviLcq9-xWBHwHLUu8iCrI6DfVBBa63gKg17gOM"

sheet_model = env["guest.tax.sheet"]
sheet = sheet_model.search([("x_sheet_url", "=", SHEET_URL)], limit=1)
product = env["product.product"].search([("name", "=", "Tiny House"), ("rent_ok", "=", True)], limit=1)
if not product:
    raise UserError(env._("Could not find the rentable product 'Tiny House'."))
if not sheet:
    sheet = sheet_model.create(
        {
            "name": "Tiny House Google Sheet",
            "x_load_method": "gog",
            "x_sheet_url": SHEET_URL,
        }
    )
sheet.write({"x_load_method": "gog", "x_product_id": product.id})

rows = sheet._rows_with_gog(SPREADSHEET_ID, gid=1105064919)

months = sorted({row["checkin"].replace(day=1) for row in rows if row["checkin"]})
for month in months:
    sheet.x_month = month
    result = sheet._create_messages_for_month(iter(rows))
    print(f"{month:%Y-%m}: {result['params']['message']}")

env.cr.commit()
print(f"Finished loading {len(months)} month(s).")
