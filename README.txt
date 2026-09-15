KICKBASE ASSISTENT – WINDOWS
Version 2026.09.15-portfolio-2
================================

INSTALLATION / UPDATE
1. ZIP vollständig entpacken.
2. INSTALLIEREN.bat starten.
3. Bestehende Anmeldung und Einstellungen bleiben erhalten.
4. Im Menü "Strategie & Deals" die neue Versionsnummer prüfen.

Installation: %LOCALAPPDATA%\KickbaseAssistent
Dashboard: http://127.0.0.1:8765
Protokoll: %LOCALAPPDATA%\KickbaseAssistent\kickbase-assistent.log
Ein Installationstest liest nur Daten und handelt nicht.
Echte Aktionen setzen den bereits vorhandenen Live-Modus voraus. Der
Testmodus zeigt Pläne, führt aber keine KICKBASE-Schreibaufrufe aus.
Zugangsdaten werden lokal über den Windows-Anmeldedatenspeicher verwaltet.
Für E-Mail einmal BENACHRICHTIGUNGEN-EINRICHTEN.bat starten.
Für privaten Handy-Zugriff FERNZUGRIFF-EINRICHTEN.bat / Tailscale verwenden.

WANN WERDEN GEBOTE ABGEGEBEN?
Standard: Marktprüfung alle 5 Minuten, während der gesamten Angebotszeit.
Der Abstand kommt zur Laufzeit der Datenabfragen hinzu; es ist kein garantierter
Sekundentakt. PC und Assistent müssen laufen.
Bei abgeschalteten Dauergeboten gilt das Zeitfenster vor Angebotsende.
Unveränderte eigene Gebote werden nicht erneut gesendet. Rücknahmen haben
Vorrang. Erst ein neuer Datenstand nach erfolgreicher Rücknahme gibt Budget
für andere Käufe frei. Die maximale Zahl an Aktionen gilt weiterhin je Lauf.
Ein geeigneter Kandidat ist nicht automatisch ein geplanter Kauf: Budget,
Kombination, Kadergrenzen, Zeitfenster und andere Aktionen können ihn verdrängen.
Das Dashboard erklärt diesen Unterschied und zeigt den nächsten ungefähren Check.

DEAL-KRITERIEN
Startelf:
- S11 mindestens nach deiner Regel, standardmäßig 3/5.
- Mindestens 2 Saisoneinsätze, durchschnittlich 45 Minuten und 50 Punkte.
- Wenn die letzten 3 Spiele vollständig vorliegen: mindestens 45 Minuten im
  Schnitt und mindestens 50 gewichtete Formpunkte aus bis zu 5 Spielen.
- Bessere Gesamtelf oder günstige Absicherung einer Reserveposition.
- Fehlende Minuten bleiben unbekannt; keine Umdeutung als 0 Minuten.

Trading:
- Positiver 24-Stunden-Marktwerttrend; KI-Trend mindestens 0.
- Kein Gamble-Signal; standardmäßig höchstens 3 Mio. Euro je Spieler.
- Zwei Tage linear fortgeschriebener Trend abzüglich Aufpreis mindestens
  100.000 Euro. Das ist eine Schätzung, kein Gewinnversprechen.
- Spieler ohne Einsätze können nur ausdrücklich als Trading infrage kommen.
- Eingeschränkte Verfügbarkeit, niedrige bekannte S11 oder aktuelle
  Risikohinweise blockieren auch solche Käufe.

Alle Käufe:
- Nicht unter Marktwert (Ligavorgabe).
- Individuelle Obergrenze: maximaler Aufpreis, positiver Base-XI Fair Value,
  geschätzte Mehrpunkte und vergleichbare Alternativen begrenzen den Preis.
- Alle offenen eigenen Gebote zählen beim Budget mit.
- Verkaufserlöse sind erst nach tatsächlichem Eingang verfügbar.
- Verlässlicher Kontostand, Kadergröße und Vereinslimit erforderlich.
- Der Kontostand stammt aus der exakt passenden Liga in /leagues/selection.
  Der Wert "b" in lineup/overview ist ausdrücklich NICHT der Kontostand.

KAUFKOMBINATIONEN UND BANK
Bis zu 24 Kandidaten und bis zu 3 Käufe je Kombination werden verglichen.
Innerhalb dieser begrenzten Auswahl erfolgt eine vollständige Kombinationensuche.
Es wird kein weltweites Optimum über alle Spieler behauptet.
Reihenfolge: besetzte gültige Positionen, fehlende Pflichtpositionen, geschätzte
Punkte und günstige Reservepositionen; bei Gleichstand niedrigerer Kaufpreis.
So können zwei günstige Verbesserungen einem teuren Star vorgezogen werden.
Alternative Kombinationen werden mit Kosten und erwarteten Punkten angezeigt.
Die Ziel-Elf ist ein Kaufvorschlag, keine bereits ausgeführte Aufstellung.

Bank: standardmäßig 2 verschiedene Reservepositionen, höchstens 4 Mio. Euro
je Bankspieler. Kader- und Vereinsgrenzen werden berücksichtigt.
Trading-Kapital gibt es erst bei vollständiger Elf. Höchstens 20% des Geldes
nach Reserve, bei fehlender Bank 10%, außerdem höchstens 5 Mio. Euro.
Vorhandene Trading-Spieler und offene Trading-Gebote zählen gemeinsam dazu.
Anhand besserer bezahlbarer Kombinationen können geeignete alte Gebote
zurückgezogen werden; standardmäßig erst ab 10 geschätzten Mehrpunkten oder
bei besserer Besetzung fehlender Pflichtpositionen.

PROGNOSEN UND QUELLEN
KICKBASE performance: tatsächliche Spieltagspunkte p und Minuten mp, maximal
die letzten 5 Spiele der laufenden Saison. ap/tp sind keine Spieltagspunkte.
Zukünftige Spiele und noch junge laufende Partien werden nicht als fertige
Leistung übernommen. Historische Startelfeinsätze stammen separat von Base-XI.
Bis zu 4 Performance-Abfragen pro Lauf; mindestens 1 Stunde Abstand je Spieler.
Nach 6 Stunden gelten nicht erneuerte Daten als veraltet.
Die Anzeige kann sich beim ersten Start deshalb über mehrere Läufe ergänzen.

Punkteprognose: 70% gewichtete aktuelle Form und 30% Saisonmittel, sofern beide
vorliegen; sonst die vorhandene Quelle. S11 und bekannte Belastung fließen ein.
Gegnerfaktor aus dem Punkteprofil der elf punktbesten Vereinsspieler laut Base-XI.
Dies ist keine Tabellenposition. Unbekannte Gegner erhalten keinen Bonus/Malus.
Die nächsten bis zu 3 Gegner werden angezeigt.
Rotation: Warnung, wenn mindestens 2 der letzten 3 Spiele unter 60 Minuten
liegen. Das beweist keine taktische Rotation und ist entsprechend bezeichnet.
Bekannte Pflichtspiele mit höchstens 4 Tagen Abstand lösen eine Belastungswarnung aus.
Internationale und Pokaltermine werden NICHT automatisch vollständig geladen.
Bestätigte zusätzliche Termine können mit Verein, Datum und Quelle im Dashboard
hinterlegt werden. Ohne diese Einträge bleibt die zusätzliche Belastung unbekannt.

Base-XI: öffentlicher Datenabruf ohne Weitergabe deiner KICKBASE-Anmeldung.
Basisdaten alle 6 Stunden; bis zu 2 ergänzende Formabfragen je Lauf.
LigaInsider-Prognosen bleiben quellenbewusst von KICKBASE getrennt.
Bei Ausfällen wird kein Wert erfunden. Ein bloßer Base-XI-Ausfall führt nicht
zur pauschalen Rücknahme aller Gebote und blockiert neue Scouting-Käufe.
Datenalter, Formwerte, Gegnerbasis, Kaufzweck und Preisobergrenze sind sichtbar.

VERKAUF UND MEHR GEWINNPOTENZIAL
Standardmäßig orientieren sich Verkaufsentscheidungen am aktuellen Markt,
nicht an einem möglicherweise zu hohen alten Einkaufspreis. Ein sinnvoller
Verkauf darf daher einen Verlust realisieren. Optional kann wieder die
Einkaufspreis-Basis gewählt werden.
Echte Gewinne/Verluste werden IMMER gegenüber dem tatsächlichen Kaufpreis gerechnet.

Trading-Kursziel standardmäßig +8%, Rückgangsgrenze 5%, Haltedauer 7 Tage.
Im Marktmodus ist der festgehaltene Marktwert bei erster Erfassung die
Bezugsgröße für diese Kursbewegung; im Einstandsmodus ist es der Kaufpreis.
Ein +8%-Kursziel ist daher nicht automatisch +8% Gewinn auf deinen Einkaufspreis.
Bei Ausstieg orientiert sich die Angebotsuntergrenze im Marktmodus am aktuellen
Marktwert. Ein Kursrückgang, negative Trends oder eine abgelaufene bekannte
Haltedauer können einen Verkauf auslösen. Keine Garantie einer Ausführung zum
Ziel- oder Grenzpreis. Höhere Ziele können längere Wartezeiten bedeuten.
Fehlt der tatsächliche Kaufzeitpunkt, wird keine Haltedauer erfunden.
Bestehende Spieler können ausdrücklich als Startelf, Trading oder Bank markiert werden.
Neue Rollen gelten beim nächsten Sync.

Länger gelistete Spieler: nach standardmäßig 3 Tagen wird der Angebotspreis
schrittweise neu bewertet, innerhalb der gültigen Preisgrenzen.
Wichtige Spieler dürfen erst verkauft werden, wenn Mindestkader und eine
vollständige gültige Elf aus bereits vorhandenen Spielern erhalten bleiben.
Mehrere Verkäufe werden gemeinsam geprüft; offene Ersatzgebote zählen nicht.
Geschützte Spieler werden nicht automatisch verkauft oder umgepreist.
Ohne bekanntes aktuelles Verkaufsangebot wird kein Sofortverkaufspreis erfunden.
Bei unbekanntem Anpfiff bleiben geschützte Verkäufe vorsorglich gesperrt.

ERKLÄRUNGEN, ERGEBNISSE UND PROBELAUF
Zu aufgezeichneten Käufen: Zweck, Entscheidungsgrund, damalige Preisgrenze,
Kaufpreis soweit verifiziert, Verkaufsziel und Haltedauer.
Ein erfolgreicher Gebotsaufruf allein ist kein nachgewiesener Kauf.
Historische Käufe vor Beginn der Aufzeichnung haben gegebenenfalls keinen
bekannten Entscheidungsgrund; dieser wird nicht nachträglich erfunden.
Realisierter Gewinn wird erst nach bestätigter Angebotsannahme UND späterer
Kaderbestätigung erfasst. Ein verschwundener Spieler allein beweist keinen
Erlös. Unbekannte Ergebnisse bleiben gesondert. Historische manuelle Verkäufe
ohne Preisnachweis werden nicht rückwirkend in eine Gewinnsumme umgedeutet.
Punkte werden als Zuwachs seit erster Beobachtung gezeigt, nicht als erfundener
Gesamtertrag seit einem unbekannten früheren Kaufdatum.
Änderungen an Marktwert, S11, Status und Minuten werden hervorgehoben.

Probelauf: separate Reserve und S11-Grenze testen, ohne echte Aufträge.
Hypothetische Warenkörbe werden aufgezeichnet und bei verfügbaren späteren
Kursen neu bewertet. Marktwertänderungen sind keine realisierten Gewinne.
Zuschläge, tatsächliche Verkäufe und eine rückwirkende Erfolgsquote werden
nicht simuliert. Probelauf-Ergebnisse ändern keine Handelsregeln automatisch.

SPIELTAG, MVP UND WINTERRESET
Prüfung: vollständiger Kader, gültige vorgeschlagene Elf, tatsächliche
Aufstellungs-IDs, Kontostand, S11-Risiken und nächster Anpfiff.
Die App setzt die Aufstellung nicht automatisch per KICKBASE-Schreibaufruf.

MVP-Regel: endgültigen MVP, Spieltag, Quelle und tatsächliches Spieltagsende
im Dashboard bestätigen. Eine unvollständige Punkteliste bestimmt keinen MVP.
Ein bestätigter eigener MVP wird als Pflichtverkauf an KICKBASE angezeigt;
Managerangebote werden dafür nicht automatisch angenommen. Den Verkauf an
KICKBASE in der KICKBASE-App durchführen und danach als erledigt bestätigen.
Der MVP wird nicht ohne verlässliche Quelle automatisch erraten.

Winterreset: vereinbarten Termin selbst einstellen; kein Datum wird erfunden.
Der Termin verkürzt bekannte Trading-Haltefristen. Neue Trading-Käufe bleiben
aus, wenn der Reset vor dem geplanten Halteende liegt. Bei vollständiger Elf
werden kurz vor dem Reset Käufe ohne belegten Einsatz davor blockiert.
Nach dem Termin warten neue Käufe auf die Aktualisierung des Datums.
Der Assistent verkauft nicht pauschal den ganzen Kader und setzt keine Liga zurück.

STUNDENMAIL
Höchstens eine automatische Sammelmail pro Stunde, auch nach Neustarts.
Bestätigte Aktionen, wichtige Probleme, Kontostand, offene Gebote, freies
Budget und erfasster realisierter Gewinn/Verlust werden zusammengefasst.
Unveränderte Fehlermeldungen/Blockaden werden nicht alle 5 Minuten neu verschickt.
Ohne neue Ereignisse keine leere Mail. Manuelle Testmails sind separat.
Fehlgeschlagene Zustellung wird frühestens nach einer Stunde erneut versucht.

TECHNISCHE PRÜFUNG UND GRENZEN
Unit-Tests prüfen Datenzuordnung, Nullwerte, Minuten, Kaufkombinationen,
Budget, Club-/Kadergrenzen, Gebotswechsel, Verkaufsschutz, Ergebnisnachweis,
Probeläufe, Regeln und Installations-Sicherheit.
Windows-CI prüft Python, JavaScript, JSON und die Importe aus dem erzeugten ZIP.
Ein DOM-Funktionstest prüft das befüllte Strategie-Dashboard.
Echte KICKBASE-Transaktionen und echte SMTP-Zustellungen wurden hier nicht
gegen deinen Account getestet. Der Windows-Anmeldedatenspeicher ist lokal.
KICKBASE-Schnittstellen sind inoffiziell dokumentiert und können sich ändern.

Implementierte Datenschemata:
https://github.com/leon-schaefer/kickflow/tree/main/src/api/kickbase
https://www.base-xi.de/players

Autostart ausschalten: Windows + R, shell:startup, Kickbase-Assistent.cmd entfernen.
