Customer Language
=================

This module adds the ``res.partner.communication_lang_id`` field to every
contact. It does not create another language table: all languages, including
inactive languages not installed for the Odoo user interface, come from
Odoo's ``res.lang`` model.

When a country is selected or changed on a contact and the customer language is
empty, the language is inferred from the country code (for example, Germany
selects ``de_DE``). OCA's **Enforce language** country setting takes priority
and can be used for multilingual countries. An explicitly selected customer
language is preserved when the country changes.
