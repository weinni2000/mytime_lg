# Camping Automation

Imports upcoming reservations from a Guesty shared "Reservations" report and creates
confirmed rental bookings (`sale.order` + `sale.order.line` + `planning.slot`) in Odoo,
twice a day via a scheduled action.

Reservations already imported (tracked via `sale.order.client_order_ref` = the Guesty
reservation id) are skipped on later runs, so re-running is safe.

## Setup

After installing the module, set the Guesty report token as a system parameter
(Settings > Technical > Parameters > System Parameters — do **not** commit it to this
repo):

- Key: `camping_automation.guesty_token`
- Value: the JWT token from the Guesty shared report link
  (`https://app.guesty.com/apps/reservations?view=...&token=...`)

The report view id, target company and the listing → product/resource/role mapping are
configured in `models/camping_guesty_sync.py` (`GUESTY_VIEW_ID`, `ODOO_COMPANY_ID`,
`LISTING_CONFIG`) — extend `LISTING_CONFIG` when more listings need to be synced.

`Tiny House` currently has no rental price configured in Odoo, so every imported order
line is created with `price_unit = 0.0` and needs manual pricing before invoicing.
