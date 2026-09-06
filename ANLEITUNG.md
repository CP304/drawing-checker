# Drawing Checker – Kurzanleitung

Für Anwenderinnen und Anwender. Zwei Seiten, mehr braucht es nicht.

## Was das Programm tut

Es holt zu jeder Materialnummer Ihrer Liste das Zeichnungspaket aus SAP
(Transaktion YMATDOCS), prüft die Zeichnung auf Vollständigkeit,
Normverstöße und fachliche Widersprüche, vergleicht sie mit dem
3D-Modell – und schreibt das Ergebnis in Ihre Excel-Tabelle zurück.

Es entscheidet **nicht**, ob eine Zeichnung freigegeben wird. Es sagt
Ihnen, wo Sie hinsehen müssen.

## In fünf Schritten

1. **Excel vorbereiten.** Eine Spalte mit den Materialnummern, eine
   Überschriftenzeile. Sonst nichts. Die Datei darf ruhig weitere Spalten
   enthalten.
2. **Programm starten**: Doppelklick auf **`Start.bat`** im
   Programmordner (oder auf die Verknüpfung „Drawing Checker" auf dem
   Desktop). Beim allerersten Start richtet sich das Programm selbst ein –
   das dauert einige Minuten, das Fenster dabei offen lassen. SAP muss
   offen und angemeldet sein; das Programm nutzt Ihre bestehende Anmeldung.
3. **Datei wählen und auf die Spalte zeigen**, in der die Materialnummern
   stehen. Das Programm zeigt eine Vorschau der erkannten Nummern.
4. **Starten.** Der Lauf arbeitet die Liste selbstständig ab. Sie können
   ihn pausieren und fortsetzen; nach einem Abbruch (auch nach einem
   SAP-Absturz oder einem Neustart des Rechners) macht er dort weiter, wo
   er stehengeblieben ist.
5. **Ergebnis ansehen.** Am Ende öffnet sich der Bericht. Die
   Ergebnis-Excel liegt neben Ihrer Ausgangsdatei mit dem Zusatz
   `_geprüft`.

## Während des Laufs

- **Die Ergebnis-Excel wächst mit.** Nach jeder Materialnummer steht die
  Zeile auf der Platte. Auch wenn der Rechner ausgeht, ist alles bis dahin
  gesichert.
- **Blockweise:** Nach je 25 Materialnummern (einstellbar) sichert das
  Programm einen Zwischenstand, schreibt den Bericht neu und räumt SAP auf.
  Der Fortschrittsbalken zeigt „Block 3 von 12".
- **Pause** hält den Lauf an, ohne etwas zu verlieren; **Abbrechen** beendet
  ihn sauber – auch mitten in einem Download.
- **Beim nächsten Start** fragt das Programm von selbst: „Zu dieser Liste
  gibt es einen unfertigen Lauf, 240 Nummern sind geprüft – dort
  fortsetzen?" Ein Klick auf Ja, und es geht genau dort weiter.
- **SAP:** Das Programm nutzt Ihre bestehende Anmeldung und öffnet
  höchstens ein eigenes Fenster – nie mehr als fünf insgesamt. Sind schon
  fünf offen, meldet es das, statt Ihnen das letzte Fenster wegzunehmen.

## Was Sie zurückbekommen

Je Materialnummer eine Zeile mit:

| Spalte | Inhalt |
|---|---|
| Status | OK / Findings / Fehlgeschlagen / Übersprungen |
| Schwerste Bewertung | K.O., Fehler, Prüfen oder Hinweis |
| Festgestellte Mängel | im Klartext, mit Regelcode |
| Letzte Änderung | das späteste Datum, das auf der Zeichnung steht |
| Fertigungsverfahren | was das Programm erkannt hat (Fräsen, Schweißen …) |
| Bild | Verweis auf die annotierte Zeichnung |
| Geprüft am | Datum und Uhrzeit der Prüfung |

Dazu im Ergebnisordner: das annotierte Zeichnungsbild je Materialnummer
(nummerierte Fundstellen mit Legende), ein HTML-Bericht mit den häufigsten
Mängeln und eine `findings.csv` für eigene Auswertungen.

## Die vier Bewertungen

- **K.O.** – Paket unbrauchbar oder das 3D-Modell passt nicht zur
  Zeichnung. Nicht anfragen, erst klären.
- **Fehler** – klare Beanstandung, die Zeichnung gehört nachgebessert.
- **Prüfen** – das Programm ist sich nicht sicher. Kurz ansehen, oft ist
  es in Ordnung.
- **Hinweis** – nur zur Information.

## Wenn etwas nicht stimmt

- **Eine Meldung wirkt falsch.** Das annotierte Bild zeigt, worauf sie sich
  bezieht. Melden Sie den Regelcode (z. B. `GT.GENERAL_TOL`) an die
  Systembetreuung – Regeln lassen sich einzeln abschalten oder anders
  bewerten, ohne das Programm zu ändern.
- **„Prüfung basiert auf OCR".** Die Zeichnung war ein Scan ohne
  Textebene. Die Erkennung ist dann unsicher, deshalb wird nichts hart als
  Fehler gemeldet. Bei Beanstandungen bitte die Zeichnung selbst ansehen.
- **Der Lauf hält an.** Meist ist die Platte voll oder SAP hängt. Die
  Meldung sagt, was zu tun ist; nach dem Beheben mit „Fortsetzen"
  weiterlaufen lassen – bereits geprüfte Zeilen bleiben erhalten.
- **Die Ergebnisdatei lässt sich nicht schreiben.** Sie ist in Excel
  geöffnet. Das Programm weicht auf eine Datei mit dem Zusatz `_neu` aus;
  besser: Excel schließen, solange der Lauf läuft.

## Wenn der Start nicht klappt

Das schwarze Fenster bleibt bei Problemen offen und nennt die Ursache im
Klartext – meist eines von dreien:

- **„Kein Python ab Version 3.10 gefunden"**: Python fehlt auf dem Rechner.
  Die Meldung nennt den Downloadlink; im Firmenumfeld über das
  Softwarecenter anfordern.
- **„Die Installation ist fehlgeschlagen"**: meist kein Zugang zum
  Paketserver (Proxy). Bitte die Datei `logs\einrichtung.log` an die
  Systembetreuung geben.
- **„Die vorhandene Umgebung ist unbrauchbar"**: passiert, wenn der Ordner
  verschoben oder kopiert wurde. Das Programm baut sie selbst neu auf;
  erzwingen lässt sich das mit `Start.bat neu`.

## Was das Programm nicht kann

- Es liest keine Konstruktionsabsicht. Ob eine enge Toleranz nötig ist,
  entscheiden Sie.
- Bei Scans ohne Textebene sieht es nur, was die Texterkennung hergibt.
- Es prüft die Zeichnung, nicht das Bauteil. Ein sauber gezeichneter
  Unsinn bleibt unentdeckt.
