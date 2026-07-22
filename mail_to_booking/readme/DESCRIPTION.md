Dieses Modul fügt einem eingehenden Mailserver (`fetchmail.server`) eine
Checkbox "Buchungen per DeepSeek erkennen" hinzu. Ist sie aktiviert, wird
jede über diesen Server eingehende E-Mail zusätzlich an die DeepSeek-API
geschickt, um zu prüfen, ob es sich um eine Camping-/Vermietungsbuchung
handelt und um die relevanten Daten (Gast, Zeitraum, Preis, Plattform, ...)
zu extrahieren.

Erkennt DeepSeek eine Buchung, wird automatisch ein Verkaufsauftrag
(`sale.order`) im Entwurf angelegt, der ursprüngliche Mailinhalt wird im
Chatter des Auftrags dokumentiert, und der Import bleibt zur Kontrolle
als `mail.to.booking`-Datensatz nachvollziehbar.

Der DeepSeek-API-Key wird als Feld auf der Firma (`res.company`) verwaltet.
Das separate Modul `mail_to_booking_settings` trägt den tatsächlichen
Schlüssel für diese Installation ein.
