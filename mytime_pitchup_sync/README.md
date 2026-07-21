# Mytime Pitchup Sync

Synchronizes Pitchup REST API bookings into Odoo rental sales orders.

Configure the **Pitchup API Key** on the company form. Use **Sync Pitchup Orders** for a
manual run. The scheduled action runs every 12 hours.

Pitch types are mapped as follows:

- `66395` → `Zeltplatz (2P)` (`product.product` 7701)
- `59292` → `Stellplatz Wohnwaagen (2P)` (`product.product` 7699)
- `60103` → `Stellplatz Van (2P)` (`product.product` 7698)

Bookings are idempotent by Pitchup booking ID. Confirmed bookings are created as rental
orders and confirmed when resources are available. If allocation fails, the order
remains in draft for manual handling. Cancelled Pitchup bookings cancel the matching
Odoo order.
