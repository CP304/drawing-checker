# Drawing Checker

Internes Tool zur automatisierten Prüfung technischer Zeichnungen je
Materialnummer: fachliche Prüfung der technischen Kommunikation nach
allgemeinen Normen (Sicht: internationaler Einkauf), Sprach-Check
(deutschsprachige Zeichnungen sind ein Finding) und Geometrieabgleich der
Zeichnung gegen das STEP-Modell (Erkennung falsch gespeicherter
Konfigurationen). Ergebnisse: annotiertes Zeichnungsbild je Materialnummer
plus Rückschrieb in eine Kopie der Input-Excel.

Konzept und Architektur: siehe [PLAN.md](PLAN.md).

## Installation (Entwicklungsrechner)

```bash
pip install -e .[occ,dev]          # occ = exakte STEP-Analyse (empfohlen)
pip install -e .[sap]              # nur Windows: SAP GUI Scripting (pywin32)
pip install -e .[ocr]              # optional: OCR für gescannte Zeichnungen
                                   # (zusätzlich Tesseract-Binary installieren)
```

Ohne `[occ]` fällt der STEP-Abgleich auf einen eingebauten
Punktwolken-Parser zurück (nur Bounding-Box, kein Volumen/Zylinder).

## Nutzung

```bash
drawing-checker                       # GUI, echtes SAP (P11), nur Windows
drawing-checker --mock mockdata/out   # GUI im Testmodus (ZIPs aus Ordner)

# Ohne GUI (Automatisierung/Tests):
drawing-checker --headless --mock mockdata/out \
    --excel mockdata/out/Materialliste_Mock.xlsx --column C
```

Ablauf in der GUI (3 Schritte): Excel wählen → Spalte mit den
Materialnummern **anklicken** → Prüfung starten. Pause/Abbruch jederzeit;
„Letzten Lauf fortsetzen“ nimmt einen abgebrochenen Lauf wieder auf
(Zustand wird nach jeder Materialnummer gespeichert).

Ergebnisse landen neben der Input-Excel:

- `<name>_geprüft.xlsx` – Ergebnis-Spalten je Zeile (Status, Findings,
  Geometrie-Vergleichswerte, Link zum Bild)
- `Ergebnisse/lauf_<zeitstempel>/<matnr>.png` – annotierte Zeichnung
  (Marker + Legende)

## Mockdaten

```bash
python -m mockdata.generate            # erzeugt mockdata/out/
```

Erzeugt realistische A3-Zeichnungen (Schweißkonsole, Gussgehäuse,
Antriebswelle) mit gezielt eingebauten Fehlern, passende bzw. absichtlich
falsche STEP-Modelle, YMATDOCS-artige ZIPs und die Input-Excel. Erwartete
Ergebnisse:

| Materialnummer | Inhalt | Erwartung |
|---|---|---|
| 10473215 | Schweißkonsole | Fehler: deutsche Anmerkungen, ISO 5817 ohne Gruppe, kein Kantenzustand; STEP passt |
| 10473216 | Gussgehäuse | K.O.: STEP ist falsche Konfiguration; zudem keine Allgemeintoleranz/Gusstoleranz |
| 10473217 | Antriebswelle | grün (vollständig, zweisprachig, STEP passt) |
| 10473218 | Antriebswelle als Scan | Warnung: kein Textlayer (OCR-Fallback), kein STEP |
| 10473219 | – | K.O.: kein Dokumentpaket vorhanden |

## Tests

```bash
python -m pytest tests/ -q            # inkl. End-to-End über die Mockdaten
```

Der End-to-End-Test simuliert auch einen SAP-Absturz (Mock) und den
Resume-Pfad.

## Regelkatalog anpassen

`drawing_checker/rules/profiles.yaml` – Regeln je Materialgruppe
(default/guss/schweiss) an-/abschalten, Severities und Toleranzbänder für
den Geometrieabgleich ändern. Profile erben per `inherit` voneinander.

## TODO für die SAP-Anbindung (sobald der .vbs-Mitschnitt vorliegt)

1. **`drawing_checker/sap/ymatdocs.py`**: die mit `# VBS:` markierten
   Element-IDs durch die echten IDs aus dem Mitschnitt ersetzen
   (Materialfeld, Ausführen-Button, Download-Button, Datei-Dialog).
   Struktur, Warte-/Fehlerlogik und Download-Überwachung sind fertig.
2. **Login klären**: SSO oder Benutzer/Passwort? Bei Passwort: Eintrag
   `drawing-checker/P11` im Windows Credential Manager anlegen
   (`SapWatchdog.store_credentials`), der Watchdog nutzt ihn beim
   automatischen Neustart.
3. **`SAPLOGON_PATH`** setzen, falls saplogon.exe nicht im Standardpfad
   liegt.
4. Erster Durchstich mit 2–3 echten Materialnummern, dann Kalibrierung der
   Checks an echten Zeichnungen (Regel-Severities in `profiles.yaml`).
5. Auslieferung: `pyinstaller --onefile --windowed -n DrawingChecker
   drawing_checker/app.py` (Windows; `rules/profiles.yaml` als Data-File
   mitgeben).
