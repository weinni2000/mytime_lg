`base_location` raises a validation error whenever a partner's or
company's country, state, city or zip does not match its selected ZIP
Location (`zip_id`). This module adds a `validate_locations` toggle on
`res.company` (Settings > General Settings > Contacts) so this check can be
switched off per company. It is disabled by default, so mismatching
addresses can be saved without error.
