This module adds a **Planning / Watching** toggle button to the Planning
schedule (Gantt) view.

- **Planning mode** (default) keeps Odoo's standard behaviour: every bookable
  resource, role and employee is shown as a row, even when it has no shift, so
  you can plan new shifts onto empty rows.
- **Watching mode** collapses the schedule down to the rows that actually
  contain a booking, giving a clean read-only overview.

A **Filter** button sits next to the toggle: it restricts the schedule to the
resources matching an editable domain (default `resource_type = material`,
i.e. bungalows, pitches, tools, ...). The domain is resolved to resource ids and
applied through Planning's `filter_resource_ids`, so empty resources stay
visible. A second button opens a domain editor prefilled with the current
domain, letting you change what the filter shows from the frontend.

All controls are available in two places: next to the **Publish** button and
next to the **Schedule** title in the Gantt grid header.
