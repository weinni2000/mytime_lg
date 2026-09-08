This module adds a "Guest Tax Sheets" configuration under *Buchung > Steuerung*.
Choose whether to load from a Google Sheet through the authenticated `gog` CLI
or from an uploaded xlsx file, then set the target month. The "Load Month"
button filters rows whose check-in date falls in that month and creates a
`guest.tax.message` for each new one (deduplicated by email + check-in date, so
re-running a load for the same month is safe).

The corresponding Tiny House rental order must already exist. The importer
matches it by check-in/check-out dates, rental product, sales channel, and—when
needed—the main guest. It enriches the order customer with missing contact and
address data and attaches guest lines for the main and additional guests. It
never creates a sale order.
