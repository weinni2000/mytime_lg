The `gog` CLI must be installed and authenticated on the Odoo server for the
account configured in the `gog_testing.gmail_account` system parameter
(defaults to `weinni2000@gmail.com`). The command used to invoke it can be
overridden via `gog_testing.gog_command` (defaults to
`/home/weinni2000/bin/gog-unlocked`), and a keyring passphrase can be set
via `gog_testing.gog_passphrase` if the credential store is locked.
