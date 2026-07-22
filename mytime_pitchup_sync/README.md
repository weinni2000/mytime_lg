# Mytime Pitchup Sync

Synchronizes Pitchup REST API bookings into Odoo rental sales orders.

Configure the **Pitchup API Key** on the company form. Use **Sync Pitchup Orders** for a
manual run. The scheduled action runs every 12 hours.

Pitch types are mapped to Booking Engine stay offer product templates. The default
wizard values derive from the existing Pitchup variant IDs and store their template:

- `66395` → template of legacy variant `7701`
- `59292` → template of legacy variant `7699`
- `60103` → template of legacy variant `7698`

Bookings are idempotent by Pitchup booking ID. Confirmed bookings are created as rental
orders and confirmed when resources are available. If allocation fails, the order
remains in draft for manual handling. Cancelled Pitchup bookings cancel the matching
Odoo order.
