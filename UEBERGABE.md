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

**Weitergabe:** `python -m tools.paket_bauen` baut `dist/DrawingChecker.zip`
– eine Datei, die alles enthält und sich beim Bauen selbst prüft. Nach jeder
Code-Änderung neu bauen, sonst verteilt man den alten Stand.

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

`mockdata/echt_quellen/` enthält **84 echte, frei lizenzierte
Fertigungszeichnungen** (28 mit STEP) aus OreSat (CERN-OHL-S v2) und
ShapeOko (CC BY-SA 3.0) – Herkunft und Auswahlkriterien in
`mockdata/echt_quellen/SOURCES.md`.

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
| `python -m tools.ocr_bench mockdata/echt_quellen` | Wie viel erkennt die OCR von einer gescannten Zeichnung wieder? |
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
