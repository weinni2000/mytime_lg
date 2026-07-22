Trägt den DeepSeek-API-Key für diese Installation über einen
`post_init_hook` auf allen bestehenden Firmen ein (Feld `deepseek_api_key`
aus dem Modul `mail_to_booking`). Firmen, die erst nach der Installation
angelegt werden, benötigen den Schlüssel manuell über das Firmenformular.

Legt außerdem den Posteingangsserver `buchungen@weingartmair.eu` als
`fetchmail.server`-Datensatz an (IMAP/SSL, `mail_to_booking_enabled`
aktiviert), falls dieser noch nicht existiert.

Dieses Modul enthält echte Zugangsdaten im Klartext und sollte nicht in
ein öffentliches Repository übernommen werden.
