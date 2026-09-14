KICKBASE ASSISTENT – WINDOWS 11
================================

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
angezeigt, per E-Mail gemeldet und als bevorzugtes Kaufziel behandelt.
Für E-Mail einmal BENACHRICHTIGUNGEN-EINRICHTEN.bat starten. Bei Gmail wird ein
Google-App-Passwort benötigt. Der Assistent prüft den Markt alle 5 Minuten und
öffentliche Nachrichten standardmäßig jede Stunde.
Nachrichten werden nach dem Veröffentlichungsdatum sortiert; die neuesten stehen
oben. Meldungen älter als 72 Stunden werden automatisch entfernt und können
keine Kaufentscheidung mehr blockieren. Automatische Gebote werden standardmäßig
erst in den letzten 10 Minuten vor Marktende abgegeben. Einstellbar sind 5, 10,
15, 20 oder 30 Minuten.
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
4. Nur bei fallendem Marktwert UND bestätigter niedriger S11-Chance sofort an
   KICKBASE verkaufen. Unbekannte S11-Werte und die beste Elf sind geschützt.

Die LigaInsider-Seitenstruktur kann sich ändern. Bei einem Abruf- oder
Zuordnungsfehler bleibt die Quelle "unbekannt"; es wird kein Wert erfunden.
