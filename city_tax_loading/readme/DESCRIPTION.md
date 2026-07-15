This module adds a "Guest Tax Sheets" configuration under *Buchung > Steuerung*,
where a Google Sheet URL (matching the guest-registration sheet used by
`city_tax/misc/internal/guestemeldung/submit_service_summary.py`) and a target
month can be set. The "Load Month" button downloads the sheet as CSV,
filters rows whose `checkin` date falls in the selected month, and creates a
`guest.tax.message` for each new one (deduplicated by email + check-in date,
so re-running a load for the same month is safe).
