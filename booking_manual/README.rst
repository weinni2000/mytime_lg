Booking Manual
==============

The public ``POST /booking/key`` webhook accepts the existing ``key`` parameter
and an SMS message in ``nachricht``. Form/query parameters and a JSON object are
supported. The webhook key may also be supplied in the HTTP ``Key`` header, as
used by Apple Shortcuts. It extracts a 4-8 digit Booking.com verification code
and stores that code in ``booking.account.temp_booking_key``.

For compatibility with common SMS forwarders, ``message``, ``body``, and
``text`` are also accepted as message field names. Messages without a code are
rejected with HTTP status 422. Webhook keys and complete SMS contents are not
written to the Odoo log.

Playwright uses a private persistent Chromium profile per ``booking.account``
under Odoo's data directory. Cookies, local storage, cache, and browser trust
state therefore survive worker restarts. The profile directory is restricted
to its operating-system owner (mode 0700).

Login attempts start at ``admin.booking.com`` so Booking.com creates a fresh
authorization flow. Saved account URLs containing the one-time ``op_token``
parameter are intentionally not reused.
