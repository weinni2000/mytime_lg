1. Firma öffnen (Einstellungen > Benutzer & Firmen > Firmen), Reiter
   "Booking Sync", DeepSeek-API-Key eintragen (oder das Modul
   `mail_to_booking_settings` installieren, das den Key automatisch setzt).
2. Unter Technisch > E-Mail > Posteingangsserver den gewünschten Server
   öffnen und "Buchungen per DeepSeek erkennen" aktivieren.
3. Neue Mails auf diesem Server werden ab sofort automatisch geprüft. Das
   Ergebnis ist unter Verkauf > Buchungen > Mail-Buchungen einsehbar.
4. Wird eine Buchung über ein gemeinsames Weiterleitungs-Postfach importiert
   (z. B. buchungen@domain.eu), muss dessen Adresse unter Verkauf >
   Buchungen > Excluded Emails eingetragen werden. Sonst wird ein neuer Gast
   fälschlich einem bereits bestehenden Kontakt zugeordnet, nur weil beide
   Buchungen über dieselbe Weiterleitungsadresse eingegangen sind - der im
   Mailtext gefundene Gastname wird dann ignoriert.
