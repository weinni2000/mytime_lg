This module adds everything needed to collect guest data for city/tourist tax
reporting and, where configured, submit it to Deskline (Feratel's guest
registration system).

**Guest data on contacts**

Each guest (``res.partner``) gets a set of city-tax fields: document
type/number/date/authority, birthdate, nationality, marketing consent, and a
salutation ("Anrede"). Age, whether the guest is a minor, and whether they're
taxable are all computed automatically from the birthdate — a manual age or a
manual "Underage" override can be used instead when no birthdate is known.

**Guest Lines and Guest Tax Messages**

A **Guest Lines** menu under *Buchung > Steuerung* lists every guest line
across all sale orders. Guest lines can also be grouped into standalone
**Guest Tax Messages** — used by the sheet import (below) to group everyone
staying together, independent of any sale order.

Each guest line shows badge-style status indicators (guest data check,
identity check, tourist tax check) so incomplete data is easy to spot, plus a
"Refresh" toggle to force these checks to recompute.

**Importing guests from a sheet**

The **Guest Tax Sheet** (*Buchung > Steuerung*) can pull guest data either
from a public Google Sheet URL or an uploaded xlsx export (e.g. from a Google
Form), matching the expected column headers, and creates a Guest Tax Message
+ sale order per stay for the target month. Re-running the import on an
already-imported sheet won't duplicate guests, but does refresh country data
in case it was wrong or missing before.

**Sending guests to Deskline**

On a sale order's *Guests* tab, or from a Guest Tax Message, use **Send to
Deskline** to submit all guests as a Deskline "Voranmeldung" (draft
registration), and **Convert to Meldeschein** to turn a submitted
Voranmeldung into a final, numbered report.

Important limitation: **a Voranmeldung can only be submitted on or before the
guest's arrival date** — Deskline rejects any submission for a stay whose
arrival date has already passed, regardless of how complete the guest data
is. In practice this means only guests who haven't arrived yet can be
registered through this module; retroactively registering a past stay isn't
supported.

Deskline access (username/password, property ID, session cookies, and the
request's base URL/header type/sub type) is configured per company under
*Settings > Companies > (a company) > Deskline*. Use **Log in to Deskline**
there to authenticate and fetch a session automatically.

Every submission and conversion attempt — successful or not — is recorded
under the **Deskline Logs** menu, showing the exact request sent and the
response received, for troubleshooting rejected submissions.
