Bootstraps a working `camping_map_booking` setup on a specific database
(intended target: `lisigruen.at`) without relying on Odoo's demo-data mode.

Installing this module pulls in `camping_map_booking` (and, through it,
`website_sale_renting`/`sale_renting`/`website_sale`), then creates the same
3 zones and 3 rental pitches shipped as demo data in `camping_map_booking`,
as regular data records instead - so `/camping/map` has something real to
show and click through on install, on a database where demo data isn't
loaded.
