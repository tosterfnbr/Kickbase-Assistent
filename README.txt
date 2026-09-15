KICKBASE ASSISTENT – WINDOWS 11
================================
Version 2026.09.15-base-xi

NEU IN DIESER VERSION
- Base-XI-Spielerstatistiken werden tatsächlich eingelesen und im neuen
  Menü "Scouting" mit Kaufzweck und Entscheidungsgrund angezeigt.
- Nachweisbar eigene ungeeignete Kaufgebote werden automatisch zurückgezogen.
- Höchstens eine automatische Sammelmail pro Stunde; keine Mail ohne neue
  Ereignisse. Marktprüfung und Handel laufen weiterhin alle 5 Minuten.
- Verkaufsaufrufe und Fehlererkennung korrigiert. Ein geplanter Kauf gilt
  beim Schutz der aktuellen Startelf nicht mehr als bereits vorhandener Ersatz.

UPDATE: ZIP vollständig entpacken und INSTALLIEREN.bat starten. Vorhandene
Anmeldung und Einstellungen bleiben erhalten. Im Menü "Scouting" steht nach
dem nächsten Sync die neue Versionsnummer. Der Installationstest handelt nicht.

1. ZIP-Datei vollständig entpacken.
2. INSTALLIEREN.bat doppelt anklicken.
3. Falls Windows fragt, die Installation von Python erlauben.
4. KICKBASE-E-Mail und Passwort nur im schwarzen Installationsfenster eingeben.

Die Zugangsdaten werden mit dem Windows-Anmeldedatenspeicher geschützt.
Sie stehen nicht in config.json oder in den Protokolldateien.

Installationsordner:
%LOCALAPPDATA%\KickbaseAssistent

Ergebnisdateien:
%LOCALAPPDATA%\KickbaseAssistent\data\markt.csv
%LOCALAPPDATA%\KickbaseAssistent\data\letzter_markt.json

Dashboard auf dem PC:
http://127.0.0.1:8765

Quellen:
Im Dashboard links "Quellen" öffnen. Dort sind LigaInsider, KBstats, Base-XI,
KickbaseNerd, die beiden TikTok-Links, YouTube und Reddit direkt anklickbar.

Live-Feed und E-Mail:
Im Dashboard links "Live-Feed" öffnen. Dort stehen neue Marktspieler, jedes
automatische Gebot/jeder Verkauf sowie neue Startelf- und Verletzungshinweise.
Auch wegen eines aktuellen Risikohinweises blockierte Gebote werden dort mit
Grund und Zeitpunkt angezeigt.
Unter "Spieler beobachten" können auch Namen eingetragen werden, die gerade
nicht auf dem Markt sind. Sobald einer davon neu erscheint, wird er mit Stern
angezeigt und in der nächsten Sammelmail gemeldet. Die Kaufkriterien gelten auch
für beobachtete Spieler.
Für E-Mail einmal BENACHRICHTIGUNGEN-EINRICHTEN.bat starten. Bei Gmail wird ein
Google-App-Passwort benötigt. Der Assistent prüft den Markt alle 5 Minuten und
öffentliche Nachrichten standardmäßig jede Stunde.
Nachrichten werden nach dem Veröffentlichungsdatum sortiert; die neuesten stehen
oben. Meldungen älter als 72 Stunden werden automatisch entfernt und können
keine Kaufentscheidung mehr blockieren. Automatische Gebote sind standardmäßig
während der gesamten Marktzeit erlaubt. Wird "Dauergebote" ausgeschaltet,
gilt das einstellbare Zeitfenster von 5 bis 30 Minuten vor Marktende.
Die S11-Chance ist ein Hauptkriterium. Standardmäßig kauft die Automatik nur
Spieler ab 3/5. Spieler mit hoher S11-Chance werden nicht wegen dieses Werts
verkauft. Kader-Marktwerte werden aus allen verfügbaren eigenen Kader- und
Aufstellungsdaten zusammengeführt; fehlende Werte erscheinen nicht als 0 Euro.
Vor jeder Passworteingabe kannst du auswählen, ob die Eingabe sichtbar oder
verborgen erfolgen soll. Sichtbar nur verwenden, wenn niemand mitlesen kann.

X-Hinweise:
Die Einrichtung fragt optional nach einem eigenen X-API-Bearer-Token. Ohne
Token bleibt X aus. Öffentliche Meldungen werden nur als unbestätigte Hinweise
behandelt: Sie blockieren für 36 Stunden automatische Käufe des betroffenen
Spielers, lösen aber niemals allein einen automatischen Verkauf aus.

Wichtig zu Quellen:
Frühere Chat-Nachrichten werden nicht automatisch auf den PC übertragen.
Bekannte Quellen und Regeln stehen in strategie.json; der Nachrichtenmonitor
nutzt öffentlich auffindbare Meldungen und verlinkt immer die Originalquelle.

Über "Daten für ChatGPT exportieren" entsteht eine aktuelle JSON-Datei ohne
Passwort oder Zugriffstoken. Diese Datei kann sicher im Chat hochgeladen werden.

Privater Zugriff vom Handy:
Nach erfolgreicher Hauptinstallation FERNZUGRIFF-EINRICHTEN.bat starten.
Tailscale anschließend auch auf dem Handy installieren und dasselbe Konto nutzen.

Protokoll:
%LOCALAPPDATA%\KickbaseAssistent\kickbase-assistent.log

Autostart deaktivieren:
Windows-Taste + R drücken, shell:startup eingeben und dort
"Kickbase-Assistent.cmd" entfernen.

WICHTIG:
Die verwendete KICKBASE-Schnittstelle ist nicht offiziell dokumentiert. Diese
Version kann nach einer bewussten Freigabe im Dashboard echte Gebote,
Preisanpassungen, Angebotsannahmen und Sofortverkäufe ausführen. Vorher bleibt
sie im Testmodus. Ein Sofortverkauf geht direkt an KICKBASE und kann nicht
rückgängig gemacht werden. Deshalb sind Startelf, Mindestkader, Mindestreserve,
Spieltagsnähe und die maximale Zahl von Aktionen automatisch begrenzt.

VERBESSERTE ENTSCHEIDUNGSLOGIK
==============================
S11 wird quellenbewusst ausgewertet: LigaInsider-Vorschau zuerst, KICKBASE als
Fallback. Ein fehlender Wert wird als "unbekannt" angezeigt und blockiert
automatische Käufe; er wird niemals als 0/5 oder als Verkaufsgrund behandelt.

Die beste Elf wird automatisch aus mehreren gültigen Formationen ermittelt.
S11-Sicherheit zählt am stärksten, danach Punkte, Marktwerttrend und Marktwert.
Die ermittelte Elf ist bei der Verkaufsstrategie geschützt.

Im Testmodus berechnet der Assistent exakt denselben Handelsplan wie im
Live-Modus, führt jedoch keinen schreibenden KICKBASE-Aufruf aus. Unter
"planned" im Export bzw. Live-Feed sind die vorgesehenen Aktionen sichtbar.

Beim Verkauf gilt die Reihenfolge:
1. Bereits gutes Angebot oberhalb der Verkaufsgrenze annehmen.
2. Sonst den Angebotspreis dynamisch aus Marktwert, Trend und S11 bestimmen.
3. Überschussspieler auf den Markt stellen.
4. Bei fallendem Marktwert UND bestätigter niedriger S11-Chance einen Verkauf
   vorbereiten. Ohne aktuellen Angebotspreis wird zunächst gelistet; es wird
   kein Sofortverkaufspreis erfunden.

Die LigaInsider-Seitenstruktur kann sich ändern. Bei einem Abruf- oder
Zuordnungsfehler bleibt die Quelle "unbekannt"; es wird kein Wert erfunden.


PORTFOLIO- UND GEWINNMODUS
==========================
Im Portfolio-Modus darf jeder nicht manuell geschützte Spieler auf den
Transfermarkt gestellt werden. Das gilt auch für Spieler der aktuell besten
Elf. Für diese Kernspieler setzt der Assistent bewusst höhere Ziel- und
Gewinngrenzen. Ein gutes Angebot für einen Kernspieler wird nur angenommen,
wenn danach der Mindestkader und eine vollständige gültige Elf aus bereits
vorhandenen Spielern bestehen bleiben. Ein offenes Kaufgebot reicht nicht.
Innerhalb des Spieltag-Schutzfensters werden neue Verkäufe blockiert.

Für Käufe bewertet der Assistent gemeinsam:
- bestätigte S11-Chance und Quelle,
- durchschnittliche und gesamte Punkte, soweit geliefert,
- Punkte pro Million Marktwert,
- Marktwerttrend,
- Kaufpreis, verfügbares Budget und Mindestreserve,
- Qualitätsgewinn gegenüber dem derzeit schwächsten Startelfspieler.

Kickbest (https://kickbest.app/) wird als optionale öffentliche Statistikquelle
abgerufen. Nur eindeutig strukturierte und eindeutig zuordenbare Spielerdaten
werden übernommen. Sind keine öffentlich auslesbaren Daten verfügbar, nutzt
der Assistent die vorhandenen KICKBASE-Statistiken und zeigt Kickbest als nicht
verfügbar an.

VERKAUFSBENACHRICHTIGUNGEN
=========================
Nach einer von der Schnittstelle bestätigten Angebotsannahme enthält die nächste
Sammelmail Spieler, Angebotspreis, berechenbaren Gewinn und Entscheidungsgrund.
Fehlgeschlagene Aufträge werden ausdrücklich als Fehler gemeldet.
Dafür einmal BENACHRICHTIGUNGEN-EINRICHTEN.bat ausführen. Im Testmodus stehen
alle geplanten Aktionen zusätzlich sichtbar im Dashboard und im JSON-Export.

BASE-XI UND GEBOTSRÜCKNAHME
===========================
Öffentliche Datenquelle: https://www.base-xi.de/api/players?comp=1
Die Integration benötigt keinen zusätzlichen Login und sendet keine
KICKBASE-Zugangsdaten an Base-XI. Zuordnung ausschließlich über die Spieler-ID.
Marktwert, 24h-/7-Tage-Trend, KI-Trend, Fair Value, Saisoneinsätze, durchschnittliche
Minuten/Punkte, Median, Punkte pro Million und Status werden übernommen.
Historische Startelfeinsätze sind keine S11-Prognose. Bei Median/Punkten pro
Million zeigt das Dashboard an, wenn Base-XI Werte aus der Vorsaison liefert.

Die Basisdaten werden beim ersten Sync und danach alle 6 Stunden aktualisiert.
Zusätzlich werden pro Durchlauf höchstens zwei öffentliche Spielerdetails für
den Punkteverlauf geladen, je Spieler mit 6 Stunden Cache. Der Verlauf erscheint
deshalb schrittweise. Die Quelle liefert dabei keine Minuten je Einzelspiel;
angezeigte Minuten sind Saisondurchschnitte. Fehlende Werte bleiben unbekannt.

Startelf-Käufe: S11 mindestens nach deiner Regel (Standard 3/5), mindestens
2 Saisoneinsätze, durchschnittlich mindestens 45 Minuten und 50 Punkte.
Auf besetzten Positionen muss der Kandidat die aktuellen Durchschnittspunkte
des schwächsten entsprechenden Startelfspielers übertreffen.
Trading-Käufe: steigender 24h-Trend, nicht negativer KI-Trend, kein Gamble-Signal,
höchstens 3 Mio. Euro pro Spieler und begrenztes Gesamtbudget. Auch Spieler ohne
Einsatz können dafür infrage kommen; im Scouting steht ausdrücklich "Trading".
Trendfortschreibung und Fair Value sind Schätzungen, keine Gewinnzusagen.

Alle offenen eigenen Gebote zählen beim verfügbaren Budget mit. Erwartete
Verkaufserlöse zählen erst nach Eingang. Pro Position wird höchstens ein neues
Startelfziel je Durchlauf angeboten. Identische bestehende Gebote werden nicht
alle 5 Minuten erneut gesendet.

Bei aktivierter Rücknahme werden auch manuell abgegebene eigene Gebote geprüft:
Verfügbarkeit/S11 verschlechtert, Preisgrenze überschritten, Kaufkriterien nicht
mehr erfüllt oder offene Gebote übersteigen Budget inklusive Reserve.
Ein bloßer Base-XI-Ausfall löst keine pauschale Rücknahme aus; neue Käufe warten.
Budget aus einer Rücknahme wird erst nach Erfolg und einer neuen Datenabfrage
für weitere Käufe genutzt. Gebotsrücknahme verkauft keinen Kaderspieler.

E-MAIL-TAKT
===========
Der erste Versand erfolgt frühestens eine Stunde nach Start der neuen Version,
danach frühestens eine Stunde nach dem letzten Versuch, jeweils beim nächsten
5-Minuten-Durchlauf. Ohne neue Ereignisse wird keine leere Mail verschickt.
Neustarts erhalten Warteschlange und Zeitgrenze. Fehlgeschlagene Zustellung
wird frühestens nach einer Stunde erneut versucht. Dieselbe unveränderte
Blockademeldung wird innerhalb von 72 Stunden nicht immer wieder verschickt.
Die manuell ausgelöste Testmail bei der Einrichtung ist davon unabhängig.

PRÜFUNG
==========
Automatische Tests prüfen Datenzuordnung, Handelsbudget, eigene/fremde Gebote,
Rücknahmen, API-Fehler und stündlichen Versand einschließlich Neustarts und
SMTP-Fehlern. Der Windows-Build prüft Python, JSON und Importe aus der ZIP.
Echte Transaktionen und der Windows-Anmeldedatenspeicher müssen auf deinem PC
mit deiner Anmeldung funktionieren; sie wurden hier nicht live ausgeführt.
