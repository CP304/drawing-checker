# Übergabe – Stand und nächste Schritte

Diese Datei ist für die **nächste Sitzung an einem anderen Rechner**
gedacht (Claude oder Mensch). Sie beantwortet: Was ist gebaut, was ist zu
tun, was muss man wissen, um nicht in dieselben Gruben zu fallen.

Stand: 06.09.2026, Branch `claude/drawing-validation-tool-inzji1`.

## 1. Was das Werkzeug heute kann

Vollständig gebaut und getestet (ohne SAP lauffähig über `--mock`):

- **98 Prüfregeln** in neun Gruppen (siehe REGELKATALOG.md), Wissen in
  YAML unter `drawing_checker/rules/` – Werkstoffe, Normen, Beschaffung.
- **Geometrieabgleich** gegen STEP über fünf unabhängige Indizien:
  Hüllmaße, Masse (Volumen × Dichte), Bohrbild, Konturprojektion (HLR)
  und Spiegelung (falsche Hand).
- **Masse-Plausibilität auch ohne STEP** (Hüllquader × Dichte).
- **OCR für gescannte Zeichnungen**, auf Zeichnungen getrimmt und messbar
  (`tools/ocr_bench.py`).
- **SAP-Anbindung ablaufgesteuert**: der .vbs-Mitschnitt wird eingelesen
  und abgespielt, nichts ist hartcodiert (SAP_DURCHSTICH.md).
- **GUI** (PySide6) mit Fortschritt, Pause/Fortsetzen, Detailansicht;
  Ergebnisse in Excel, HTML-Bericht, findings.csv, annotierte Bilder.
- **Dauerlauf-Haushalt**: Pakete werden nach der Prüfung gelöscht,
  Plattenplatz überwacht, Speicher wird freigegeben.

## 2. Das Wichtigste zuerst: der SAP-Durchstich

**Ohne den .vbs-Mitschnitt der Transaktion YMATDOCS läuft nichts im
Echtbetrieb.** Die komplette Anleitung steht in **SAP_DURCHSTICH.md** –
dort anfangen. Kurzform:

```bat
python -m drawing_checker.app --sap-import-vbs ymatdocs.vbs
python -m drawing_checker.app --sap-dry-run 10473215
python -m drawing_checker.app --sap-test   10473215
python -m drawing_checker.app                      # GUI-Dauerlauf
```

Bei Problemen: `--sap-dump` zeigt den Elementbaum des aktuellen SAP-Bildes;
ein fehlgeschlagener `--sap-test` schreibt automatisch eine Diagnose.

### Nur der Mitschnitt

Alles, was das Werkzeug über die Transaktion weiß, kommt aus der `.vbs`:
Transaktionscode, Felder, Werte, Download-Auslöser, Datei-Dialog und (bei
`OpenConnection`) das SAP-System. `vbs_parser.uebernehmen()` bündelt
Einlesen + Speichern + Kurzbericht für GUI und CLI;
`vbs_parser.kurzbericht()` sagt, ob der Ablauf brauchbar ist
(Materialnummer-Feld UND Download-Schritt erkannt). Die GUI ruft
`_ablauf_uebernehmen()` (ohne Dialoge, damit prüfbar) und legt die
Meldungen nur darum herum.

## 3. Umgebung einrichten (neuer Rechner)

**Weitergabe:** Es gibt zwei Fassungen, beides *eine* Datei:

```bash
python -m tools.einzeldatei     # dist/DrawingChecker_Setup.bat - Doppelklick,
                                # entpackt sich selbst und startet Start.bat
python -m tools.paket_bauen     # dist/DrawingChecker.zip - entpacken, Start.bat
```

Beide prüfen sich beim Bauen selbst (entpacken, `--check-rules` im entpackten
Stand). Die .bat ist der bequemere Weg, die ZIP der virenscannerfreundliche.
Nach jeder Code-Änderung **beide** neu bauen, sonst verteilt man den alten
Stand.

**Windows-Anwenderrechner:** Doppelklick auf `Start.bat` – richtet alles
ein und startet. `Start.bat neu` baut die Umgebung neu auf, `Start.bat
pruefen` lässt die Testsuite laufen. Das Skript ist bewusst ohne Umlaute
geschrieben (Codepage) und wird von `tests/test_startskript.py` gegen die
klassischen Batch-Fallen geprüft (Blockklammern, Sprungziele, verzögerte
Expansion) – dort weitermachen, wenn es erweitert wird.

**Entwicklungsrechner:**

```bash
pip install -e .[occ,ocr,dev]        # OCP für STEP, pytesseract für OCR
python -m pytest tests/ -q           # muss vollständig grün sein
python -m drawing_checker.app --check-rules
python -m drawing_checker.app --ocr-check
```

Zusätzlich nötig:

- **Tesseract** (nur für gescannte Zeichnungen): Windows über die
  UB-Mannheim-Distribution, Sprachen **deu + eng** mitwählen; Linux
  `apt-get install tesseract-ocr tesseract-ocr-deu`. Ohne Tesseract laufen
  alle anderen Prüfungen weiter, die OCR-Tests werden übersprungen.
- **pywin32** und SAP GUI Scripting (nur Windows, nur für den Echtbetrieb).
- Ohne Anzeige: `QT_QPA_PLATFORM=offscreen` setzen.

Mockdaten werden von den Tests selbst erzeugt (`tests/conftest.py`);
`python -m mockdata.generate` legt sie in `mockdata/out/` ab.

## 4. Wie hier gearbeitet wird (Konventionen, die zählen)

- **Sprache Deutsch** in Code, Docstrings, Findings, Commit-Messages.
- **Fachwissen gehört in YAML**, nicht in den Code. Neue Werkstoffe,
  Normen, Formulierungen in `drawing_checker/rules/*.yaml` ergänzen und
  `--check-rules` laufen lassen.
- **Jede neue Regel**: Code in `rules/profiles.yaml` registrieren,
  Severity dort pflegen, mindestens ein Positiv- und ein Negativtest, und
  im REGELKATALOG.md eintragen (ein Test erzwingt das).
- **Unsicheres meldet „Prüfen", nie hart „Fehler".** Bei OCR-Grundlage
  wird jede Meldung automatisch heruntergestuft.
- **Vor jedem Push**: `python -m pytest tests/ -q` und `--check-rules`.

## 5. Womit Regeln kalibriert werden

`mockdata/echt_quellen.zip` enthält **84 echte, frei lizenzierte
Fertigungszeichnungen** (28 mit STEP) aus OreSat (CERN-OHL-S v2) und
ShapeOko (CC BY-SA 3.0) – Herkunft und Auswahlkriterien in
`mockdata/echt_quellen/SOURCES.md`. Sie liegen bewusst als **ein** Archiv im
Repository; `python -m mockdata.quellen` packt sie nach
`mockdata/.echt_quellen/` aus (nicht im Repository), die Werkzeuge unten tun
das bei Bedarf von selbst. Bitte nicht wieder als Einzeldateien einchecken.

```bash
python -m mockdata.inject_errors mockdata/echt_quellen /tmp/kal
python -m drawing_checker.app --headless --mock /tmp/kal \
    --excel /tmp/kal/Materialliste_Echt.xlsx --column C
python -m tools.kalibrier_auswertung /tmp/kal
```

Die Auswertung trennt **Fehlalarm-Verdacht** (harte Meldungen auf den
unveränderten Referenzzeichnungen) von **Trefferleistung** (Regeln, die nur
auf den Fehlerpaketen anschlagen). Genau dieser Lauf hat zuletzt drei echte
Schwächen aufgedeckt:

- `WELD_CONTEXT` enthielt ein freies `a\d+` und machte aus 21 gefrästen
  Teilen „Schweißteile" (Zeichnungsnummern wie `SM-YA01`).
- Der Geometrieabgleich meldete K.O., wenn nur das Gesamtmaß auf der
  Zeichnung fehlte – jetzt entscheidet die Richtung der Abweichung.
- Allgemeintoleranzen als Freitext („Tolerance unless otherwise noted:
  +/- 0.25mm") wurden nicht erkannt.

**Merke: Ohne echte Fremdzeichnungen findet man solche Fehler nicht.**
Wenn mehr Material gebraucht wird: Open-Hardware-Repos klonen und mit
einem Textlayer-Filter nach Zeichnungen durchsuchen (Vorgehen in
SOURCES.md beschrieben). Nur permissive Lizenzen aufnehmen – keine
NC-Lizenzen, keine Händler-Katalogblätter.

## 5b. Laufsteuerung (neu)

- `RunConfig.batch_size` (25), `batch_pause_s`, `max_sap_sessions` (5).
- `Orchestrator._blockwechsel()` sichert je Block und ruft den optionalen
  Adapter-Haken `blockwechsel()`; `SapGuiAdapter` räumt dort Dialoge weg,
  springt zurück aufs Selektionsbild und prüft die Fensterzahl.
- Abbruch: `stop_event` wird an den Adapter gereicht und von dort an
  `play()` und `DownloadWatcher.wait()`; beide brechen sofort ab
  (`script_flow.Abgebrochen`). Die laufende Materialnummer wird bewusst
  NICHT gespeichert, damit sie beim Fortsetzen erneut drankommt.
- `state.finde_fortsetzbaren_lauf(config)` sucht den passenden Lauf über
  Datei + Blatt + Spalte statt "neuester Ordner".

## 6. Messwerkzeuge

| Werkzeug | Frage, die es beantwortet |
|---|---|
| `python -m tools.langlauf --count 200` | Läuft das Tool stundenlang stabil? Speicher, Platte, Zeit je Materialnummer |
| `python -m tools.ocr_bench` | Wie viel erkennt die OCR von einer gescannten Zeichnung wieder? |
| `python -m tools.kalibrier_auswertung <ordner>` | Wie viele Fehlalarme produzieren die Regeln? |
| `python -m drawing_checker.app --list-rules` | Was ist je Profil aktiv? |

Die Langlaufmessung hat zwei echte Speicherlecks gefunden (OpenCascade-
Leser und der interne Zwischenspeicher von PyMuPDF). Beide sind behoben;
wer an `ocr.py`, `step_compare.py` oder `annotate.py` arbeitet, sollte die
Messung danach wiederholen.

## 7. Was als Nächstes ansteht (Priorität)

1. **SAP-Durchstich mit echten Materialnummern** – alles andere ist
   nachrangig, solange das nicht läuft.
2. **Kalibrierung an echten Firmenzeichnungen**: 20–30 echte
   YMATDOCS-Pakete durchlaufen lassen, Fehlbefunde ansehen, Severities und
   Schwellen in `rules/profiles.yaml` nachziehen. Das bringt mehr als jede
   neue Regel.
3. **Wandstärkenprüfung aus dem STEP** (Guss/Blech/Kunststoff) – braucht
   Ray-Casting über OCP, Grundlage liegt.
4. **Laufstatistik über mehrere Läufe** aus den `findings.csv`: welche
   Regeln, welche Materialgruppen, welche Zeichner dominieren.
5. **Durchsatz**: SAP-Download des nächsten Materials parallel zur Prüfung
   des aktuellen (COM ist apartmentgebunden – SAP muss im selben Thread
   bleiben, die Prüfung kann in einen Worker).

## 8. Stolpersteine, die schon Zeit gekostet haben

- **OCP heißt je nach Python-Fassung anders.** Python 3.10 bekommt
  cadquery-ocp 7.9 (die letzte dafür gebaute), 3.11+ bekommt 8.x. In 7.9
  fehlt `Bnd_Box.GetXMin()`; deshalb liest `step_compare._box_bounds()`
  über `CornerMin()/CornerMax()`. Wer OCP-Aufrufe ergänzt, prüft sie
  gegen BEIDE Fassungen – sonst läuft das Werkzeug auf dem Zielrechner
  nicht, obwohl hier alles grün ist.
- **OCP-Namen**: `TopoDS.Face` funktioniert in beiden Fassungen
  (`Face_s` gibt es nur in 7.9).
- **OpenCascade und PyMuPDF geben Speicher nicht von selbst frei** – siehe
  `core/housekeeping.release_memory()`.
- **Mockzeichnungen taugen nicht zur Kalibrierung.** Alles, was auf
  selbstgebauten Musterzeichnungen funktioniert, kann an echten
  Zeichnungen krachend scheitern.
- **Regex ohne Wortgrenze** ist auf Zeichnungen gefährlich: Zeichnungs-
  und Positionsnummern sehen aus wie Maße und Symbole.
- **PDF-Textlayer ist nicht zeilenweise sortiert**; für Kontextprüfungen
  immer über `pdf.blocks()` gehen, nicht über den rohen Volltext.
- **Findings mit `bbox`** landen im annotierten Bild – wo immer möglich
  eine Fundstelle mitgeben, sonst steht die Meldung ohne Bezug da.

---

# Anhang: ursprüngliche Planung

Historisch, aber nützlich: Warum die Bausteine so
geschnitten sind, welche Bibliotheken warum gewählt
wurden und welche Prüfungen von Anfang an vorgesehen
waren.

Internes Tool zur automatisierten Prüfung technischer Zeichnungen je Materialnummer:
fachliche Prüfung der technischen Kommunikation / Vollständigkeit ("der Check") sowie
Geometrieabgleich gegen die zugehörige STEP-Datei (Erkennung falsch gespeicherter
Konfigurationen). Ergebnisse werden als annotierter Zeichnungs-Screenshot und als
Rückschrieb in die Input-Excel je Materialnummer ausgegeben.

---

## 1. Zielbild / Ablauf aus Anwendersicht

1. Anwender startet das Tool (Windows-Desktop-App, keine Installation von Fachwissen nötig).
2. Anwender lädt die Excel-Datei einer Materialgruppe hoch (Datei-Dialog oder Drag & Drop).
3. Tool zeigt eine Vorschau der Tabelle; Anwender **klickt auf die Spalte** mit den
   Materialnummern (kein Eintippen von Spaltenbuchstaben).
4. Anwender klickt „Prüfung starten".
5. Tool arbeitet die Liste **sukzessive und vollautomatisch** ab:
   - je Materialnummer: SAP-GUI-Report über Transaktion `YMATDOCS` (P11) →
     **ZIP-Download** eines Datenpakets,
   - ZIP entpacken: **PDF (immer, Prüfgrundlage)**, **STEP (manchmal → dann
     Geometrieabgleich)**, native CAD-Daten (werden ignoriert),
   - Checks ausführen,
   - Zeichnungsbild (gerendertes PDF) annotieren und ablegen,
   - Ergebnis in die Excel-Zeile der Materialnummer schreiben.
6. Fortschrittsanzeige (x von n, aktuelle Materialnummer, Fehlerzähler), Pause/Abbruch möglich.
7. Bei SAP-Absturz: Tool erkennt das, **öffnet P11 automatisch neu**, meldet sich an
   (bzw. SSO) und setzt bei der nächsten unverarbeiteten Materialnummer fort.
8. Am Ende: Ergebnis-Excel (Kopie der Input-Datei mit Ergebnis-Spalten) + Ordner mit
   annotierten Screenshots, Zusammenfassungs-Dialog.

---

## 2. Architektur

```
+---------------------------------------------------------------+
| GUI (PySide6)                                                 |
|  - Datei wählen, Spalte anklicken, Start/Pause/Stop           |
|  - Fortschritt, Log-Ansicht, Ergebnisübersicht                |
+------------------------------+--------------------------------+
                               | Qt-Signale (thread-safe)
+------------------------------v--------------------------------+
| Orchestrator (Worker-Thread)                                  |
|  - Job-Queue über alle Materialnummern                        |
|  - Zustandsdatei (Resume nach Absturz)                        |
|  - Retry-Logik, Fehlerklassifizierung                         |
+---------+-----------------+----------------+------------------+
          |                 |                |
+---------v------+ +--------v-------+ +------v---------------+
| SAP-Adapter    | | Check-Engine   | | Reporting            |
| - GUI Scripting| | - Zeichnungs-  | | - Screenshot-        |
|   (win32com)   | |   checks       | |   Annotation (Pillow)|
| - YMATDOCS     | | - STEP-Ab-     | | - Excel-Rückschrieb  |
| - Watchdog +   | |   gleich       | |   (openpyxl)         |
|   P11-Restart  | |                | | - Logdatei           |
+----------------+ +----------------+ +----------------------+
```

### Modulschnitt (Repo-Layout)

```
drawing_checker/
├── app.py                  # Einstieg, startet GUI
├── gui/
│   ├── main_window.py      # Hauptfenster, Wizard-artiger Ablauf
│   ├── table_preview.py    # Excel-Vorschau mit klickbarer Spaltenwahl
│   └── progress_view.py    # Fortschritt, Live-Log, Ergebnisliste
├── core/
│   ├── orchestrator.py     # Abarbeitung der Liste, Resume, Retries
│   ├── state.py            # Persistenter Lauf-Zustand (JSON je Lauf)
│   ├── package.py          # ZIP aus YMATDOCS entpacken, PDF/STEP/native klassifizieren
│   └── models.py           # Datenklassen: MaterialJob, CheckResult, Finding
├── sap/
│   ├── session.py          # Verbindung, Session-Handling, Login P11
│   ├── ymatdocs.py         # Transaktionsablauf inkl. ZIP-Download (aus dem .vbs portiert)
│   └── watchdog.py         # Absturz-Erkennung + automatischer Neustart
├── drawing/
│   ├── pdfdoc.py           # PDF laden (PyMuPDF): Textlayer, Vektoren, Rendering
│   ├── ocr.py              # Tesseract-Fallback für gescannte PDFs
│   └── dimensions.py       # Maß-/Toleranzextraktion aus dem PDF (für STEP-Abgleich)
├── checks/
│   ├── base.py             # Check-Interface, Findings mit Koordinaten (PDF-Koordinaten)
│   ├── drawing_checks.py   # Fachliche Checks techn. Kommunikation (Normenkatalog)
│   ├── language_check.py   # Deutschsprachige Beschriftung → Finding (int. Einkauf)
│   └── step_compare.py     # Geometrieabgleich: STEP vs. aus Zeichnung ermittelte Maße
├── report/
│   ├── annotate.py         # Gerendertes Zeichnungsbild + Marker/Legende (Pillow)
│   └── excel_writer.py     # Ergebnis-Spalten in Input-Excel (openpyxl)
├── config.py               # Pfade, SAP-System, Timeouts, Check-Konfiguration
└── logging_setup.py
```

---

## 3. Technologie-Entscheidungen

| Thema | Entscheidung | Begründung |
|---|---|---|
| Sprache | Python 3.11+ | Vorgabe, gutes Ökosystem für alle Bausteine |
| GUI | **PySide6** | Modern, Tabellen-Widgets für die Spaltenwahl, Threads sauber integrierbar; tkinter wäre für „bedienerfreundlich" zu limitiert |
| SAP-Anbindung | **SAP GUI Scripting API** via `pywin32` (COM) | Das ist genau das, was der .vbs-Mitschnitt liefert; 1:1 nach Python portierbar |
| Excel | `openpyxl` (+ `pandas` nur zum Einlesen der Vorschau) | Rückschrieb in die Original-Datei inkl. Formatierung |
| PDF lesen/rendern | `PyMuPDF` (fitz) | Textlayer + Vektordaten extrahieren, Seite hochauflösend als Bild rendern (ersetzt den Fenster-Screenshot: bessere Qualität, exakte Koordinaten für die Annotation) |
| OCR-Fallback | `Tesseract` (deu+eng) | Falls das PDF nur gescannt/gerastert ist und keinen Textlayer hat |
| Spracherkennung | `lingua` / `langdetect` | Erkennung deutschsprachiger Beschriftungen (Finding für internationalen Einkauf) |
| Annotation | `Pillow` | Rechtecke/Nummern/Legende auf das gerenderte Zeichnungsbild |
| STEP-Lesen | `cadquery-ocp` / `pythonocc-core` (OpenCascade) | STEP parsen, Maße/Bounding-Box/Volumen extrahieren |
| ZIP-Handling | Stdlib `zipfile` | Paket aus YMATDOCS entpacken, Dateitypen klassifizieren (PDF/STEP/native) |
| Packaging | `PyInstaller` (eine .exe) | Nicht-technische Nutzer, keine Python-Installation |
| Ziel-OS | Windows (zwingend) | SAP GUI Scripting existiert nur dort |

---

## 4. Kernbausteine im Detail

### 4.1 GUI (bedienerfreundlich, für Nicht-Techniker)

- Drei-Schritte-Wizard: **1) Datei wählen → 2) Spalte anklicken → 3) Start**.
- Spaltenwahl: Tabelle rendert die ersten ~50 Zeilen; Klick auf einen Spaltenkopf
  markiert die Spalte, Tool validiert sofort („412 Materialnummern erkannt,
  3 Zeilen leer/ungültig – werden übersprungen").
- Während des Laufs: Fortschrittsbalken, aktuelle Materialnummer, Ampel-Liste der
  bereits geprüften Nummern (grün = ok, gelb = Findings, rot = Prüfung fehlgeschlagen).
- Keine Stacktraces für den Anwender – Fehler in Klartext, Details ins Logfile.
- Buttons: Pause, Fortsetzen, Abbrechen, „Ergebnisordner öffnen".

### 4.2 SAP-Adapter (`sap/`)

- Verbindung über `GetObject("SAPGUI")` → `ScriptingEngine` → vorhandene oder neue
  Session auf **P11**.
- `ymatdocs.py` kapselt den kompletten Transaktionsablauf **bis zum ZIP-Download**.
  **Der morgen erstellte .vbs-Mitschnitt ist die Referenz** – er wird mechanisch
  nach Python portiert (gleiche Element-IDs), ergänzt um Waits/Existenzprüfungen
  statt fixer Sleeps. Zusätzlich abzudecken: der SAP-Datei-Dialog beim Download
  (Zielpfad je Materialnummer setzen, „Datei existiert"-Dialog, Warten bis das
  ZIP vollständig geschrieben ist – Größe stabil / kein Lock).
- `core/package.py` entpackt das ZIP in einen Arbeitsordner je Materialnummer und
  klassifiziert den Inhalt:
  - **PDF** → Prüfgrundlage (immer erwartet; fehlt es → Finding „keine Zeichnung im Paket").
  - **STEP** (.stp/.step) → Geometrieabgleich wird ausgeführt; fehlt es → Hinweis
    „kein STEP vorhanden, Geometrieprüfung entfällt" (kein Fehler).
  - **Native CAD-Daten** (CATPart, prt, …) → werden ignoriert.
  - Mehrere PDFs im Paket → Heuristik/Konfiguration, welches die Zeichnung ist
    (z. B. Dateiname enthält Zeichnungsnummer); im Zweifel alle prüfen und das
    kennzeichnen.
- Jeder Schritt mit Timeout und definierter Fehlerklasse:
  - *Material nicht gefunden / kein Paket / leeres ZIP* → fachliches Finding,
    weiter mit nächster Nummer.
  - *Session tot / COM-Fehler / SAP-Fenster weg / Download hängt* → Watchdog-Fall.

### 4.3 Watchdog & automatischer P11-Neustart

- Erkennung: COM-Aufruf wirft Exception, Session-Objekt nicht mehr gültig,
  `Busy`-Timeout überschritten oder SAP-Prozess (`saplogon.exe`) beendet.
- Reaktion:
  1. Aktuellen Job als „unverarbeitet" zurück in die Queue.
  2. Restliche SAP-Prozesse sauber beenden (`taskkill` nur auf SAP-Prozesse).
  3. `saplogon.exe` starten, per Scripting `OpenConnection("P11", True)`.
  4. Login (SSO; falls Credentials nötig → einmalige Eingabe in der GUI,
     Ablage im Windows Credential Manager, **nie** im Klartext).
  5. Exponentielles Backoff (max. n Versuche), danach Lauf pausieren + Meldung.
- Der Lauf-Zustand (`state.py`) wird nach **jeder** Materialnummer auf Platte
  geschrieben → auch ein Absturz des Tools selbst ist per „Fortsetzen" heilbar.

### 4.4 Check-Engine (`checks/`)

Einheitliches Interface: Jeder Check liefert `Finding(code, severity, text, bbox?)`.
`bbox` in **PDF-Koordinaten** – die Annotation rechnet sie auf das gerenderte Bild um.

Arbeitsgrundlage ist das PDF aus dem YMATDOCS-Paket:
- **Textlayer vorhanden** (Vektor-PDF aus dem CAD): Textextraktion mit Positionen
  über PyMuPDF – der Normalfall, präzise und schnell.
- **Kein Textlayer** (gescannt/gerastert): OCR-Fallback (Tesseract, deu+eng) mit
  Wort-Bounding-Boxen; Ergebnis wird als „OCR-basiert, eingeschränkte
  Zuverlässigkeit" gekennzeichnet.

**a) Zeichnungs-Checks – Prüfung nach allgemeinen Normen, aus Sicht des
internationalen Einkaufs.** Der Katalog ist umfangreich und wird als
**konfigurierbare Regelliste (YAML)** gebaut (Regeln je Materialgruppe
an-/abschaltbar, Severities anpassbar). Geplante Regelgruppen:

1. **Schriftfeld / Title Block** (ISO 7200): Benennung, Zeichnungsnummer,
   Änderungsindex, Maßstab, Werkstoff/Halbzeug, Blattangabe, Freigabe-/Datumsfelder,
   Ersteller vorhanden.
2. **Allgemeintoleranzen**: Angabe vorhanden und gültig referenziert
   (ISO 2768-1/-2 bzw. ISO 22081 mit allgemeiner Größenmaß-/Geometrietoleranz);
   Tolerierungsgrundsatz erkennbar (ISO 8015 / Hüllbedingung).
3. **GPS/Form- und Lagetolerierung** (ISO 1101): Bezüge definiert, wenn
   Lagetoleranzen verwendet; keine Toleranzrahmen ohne Bezug, wo einer nötig ist.
4. **Oberflächen** (ISO 21920, ehem. ISO 1302): Oberflächenangabe vorhanden
   (mindestens Sammelangabe); Kantenzustand (ISO 13715).
5. **Darstellung** (ISO 128 / ISO 5456): Projektionsmethoden-Symbol vorhanden
   (1. oder 3. Winkel eindeutig – für internationale Lieferanten kritisch);
   Maßeintragung nach ISO 129-1 plausibel (Einheit mm deklariert oder normkonform).
6. **Sprache – K.O.-Kriterium für internationalen Einkauf**: rein
   **deutschsprachige Beschriftungen sind ein Finding**. Erkennung: extrahierte
   Textblöcke (ohne Zahlen, Normbezeichnungen, Kürzel) werden sprachklassifiziert;
   deutsche Textblöcke ohne englische Entsprechung werden einzeln markiert
   (bbox je Textblock → direkt im Bild sichtbar). Zweisprachig ist ok.
7. **Schweiß-/Gussspezifisch** (wo zutreffend): Schweißsymbole nach ISO 2553
   mit Nahtangabe, Schweißnahtgüte (ISO 5817) referenziert; bei Gussteilen
   Gusstoleranzen (ISO 8062) und Bearbeitungszugaben angegeben.
8. **Konsistenz**: Materialnummer/Zeichnungsnummer auf der Zeichnung passt zur
   angefragten Materialnummer aus der Excel.

Umsetzung als Mix aus Mustererkennung im Textlayer (Regex auf Normbezüge,
Toleranzsyntax, Symbole als Unicode/Fonts) und Layout-Heuristiken (Schriftfeld
unten rechts, Projektionssymbol). Regeln, die auf der Zeichnung nicht sicher
entscheidbar sind, melden „nicht nachweisbar" (gelb) statt hart „fehlt" (rot).

**b) STEP-Abgleich (`step_compare.py`) – STEP gegen die aus der Zeichnung
ermittelte Geometrie** (Ziel: falsch gespeicherte Konfigurationen erkennen):

1. `drawing/dimensions.py` extrahiert Maßzahlen aus dem PDF-Textlayer
   (Regex auf Maß-/Toleranzsyntax: `⌀`, `R`, `M`, `±`, Passungen, Grenzmaße)
   inkl. Position.
2. Aus den Maßen werden die **Hüllmaße der Zeichnung** geschätzt: die größten
   konsistenten Längenmaße je Richtung (Heuristik: größte Maße dominieren die
   Außenkontur) → erwartete Bounding-Box.
3. STEP laden (OpenCascade): exakte Bounding-Box (inkl. Ausrichtung über
   Hauptträgheitsachsen, damit die Orientierung keine Rolle spielt), Volumen,
   Oberflächenzahl.
4. Vergleich mit konfigurierbarer Toleranz (relativ + absolut). Zusätzlich
   Plausibilität: jedes große Zeichnungsmaß sollte ≤ STEP-Diagonale sein;
   ⌀-Maße gegen erkannte Zylinderflächen im STEP prüfbar (Ausbaustufe).

**Grenzen bewusst einplanen (Guss-/Schweißteile):** Beim Gussrohteil vs.
Fertigteil-STEP oder bei Schweißbaugruppen weichen Hüllmaße systematisch ab
(Zugaben, Verzug, Nahtaufbau). Deshalb:
- Toleranzband je Materialgruppe konfigurierbar (Guss großzügiger),
- Ergebnis dreistufig: **passt / passt nicht / nicht sicher bewertbar** –
  „nicht sicher bewertbar" ist ein ehrliches Ergebnis und landet gelb in Excel
  statt als falscher Alarm,
- die extrahierten Vergleichswerte (Zeichnungsmaße vs. STEP-Maße) werden in die
  Excel geschrieben, damit der Anwender die Entscheidung nachvollziehen kann.
- Ausbaustufe später: bildbasierter Abgleich (Konturprojektion des STEP gegen
  die Zeichnungsansichten) für die schwierigen Fälle.

### 4.5 Reporting (`report/`)

- **Zeichnungs-Annotation:** Die PDF-Seite wird hochauflösend gerendert
  (PyMuPDF, ~200 dpi); nummerierte Marker an den `bbox`-Positionen, Legende am
  Rand (Nr. → Findingtext), Ampelfarbe je Severity. Findings ohne Position
  (z. B. „Angabe fehlt") erscheinen nur in der Legende.
  Ablage: `Ergebnisse/<Lauf-Zeitstempel>/<Materialnummer>.png`.
- **Excel-Rückschrieb:** Ergebnis-Spalten werden rechts angefügt
  (Status, Anzahl Findings, Findingtexte, Link zum Screenshot).
  Original bleibt unangetastet – geschrieben wird in eine Kopie
  `<Dateiname>_geprüft.xlsx` (vermeidet Konflikte, wenn Datei geöffnet ist).

---

## 5. Geklärte und offene Punkte

**Geklärt:**
- YMATDOCS liefert ein **ZIP-Paket**: PDF immer, STEP manchmal (dann prüfen),
  native CAD-Daten irrelevant.
- Prüfung **nach allgemeinen Normen, umfangreich**, aus Sicht des internationalen
  Einkaufs; **deutschsprachige Zeichnungen sind ein Finding** (Sprach-Check).
- STEP wird gegen die **aus der Zeichnung ermittelte Geometrie** geprüft; Guss-
  und Schweißteile sind dabei → dreistufiges Ergebnis + konfigurierbare
  Toleranzen je Materialgruppe (siehe 4.4 b).
- SAP GUI Scripting ist **freigeschaltet**.

**Offen (klärt sich morgen am .vbs):**
1. Exakter Transaktionsablauf und **wie der ZIP-Download abläuft** (Datei-Dialog?
   fester Zielpfad? Dateibenennung des ZIP?).
2. **Login P11**: SSO oder Benutzer/Passwort beim automatischen Neustart.
3. Ein **Beispiel-ZIP** (PDF + STEP, gern ein Gussteil und ein normales Teil)
   wäre ideal, um Textlayer-Qualität und Maßextraktion früh an echten Daten zu
   verproben – davon hängt die Treffsicherheit der Checks maßgeblich ab.

---

## 6. Meilensteine

| # | Meilenstein | Inhalt |
|---|---|---|
| M1 | Gerüst & GUI-Durchstich | Repo-Struktur, PySide6-Wizard, Excel laden, Spaltenwahl per Klick, Dummy-Lauf mit Fortschritt |
| M2 | PDF/STEP-Pipeline offline | ZIP entpacken/klassifizieren, PDF-Textextraktion + Rendering, OCR-Fallback, STEP-Bounding-Box – testbar mit Beispiel-ZIPs **ohne SAP** |
| M3 | SAP-Durchstich | .vbs → `ymatdocs.py`, eine Materialnummer end-to-end: Report ausführen, ZIP herunterladen |
| M4 | Robustheit | Watchdog, P11-Auto-Neustart, Resume-Zustand, Dauerlauf über echte Liste |
| M5 | Checks v1 | Normen-Regelkatalog (YAML-konfigurierbar), Sprach-Check, STEP-Abgleich mit Maßextraktion |
| M6 | Reporting | Annotation, Excel-Rückschrieb, Ergebnisordner, Abschlussdialog |
| M7 | Auslieferung | PyInstaller-.exe, Kurzanleitung mit Screenshots, Pilot mit einer Materialgruppe |

M1 und M2 sind **ohne SAP** entwickel- und testbar (Beispiel-ZIPs genügen) und
können sofort starten; M3 beginnt, sobald der .vbs-Mitschnitt vorliegt. Die
Check-Qualität (M5) wird iterativ an echten Zeichnungen kalibriert – erst wenige
Materialnummern mit manueller Kontrolle, dann Ausweitung.
