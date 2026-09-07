# Drawing Checker – Hinweise für Claude-Sessions

Internes Windows-Tool: prüft technische Zeichnungen je SAP-Materialnummer
(YMATDOCS-ZIP mit PDF + optional STEP) auf Normverstöße, fachliche
Widersprüche und Geometrie-Mismatch. GUI für nicht-technische Anwender.
Sprache im Code/UI: Deutsch (Docstrings, Findings, Commit-Messages).

**Das Repository ist bewusst konsolidiert.** Wenige, größere Dateien statt
vieler kleiner: 20 Module im Paket, 6 Testdateien, 2 Werkzeuge, 3
Dokumente. Nicht wieder aufsplitten – neue Funktionen kommen in das
thematisch passende Modul, neue Tests in die passende Testdatei.

## Kommandos

```bash
pip install -e .[occ,dev]                  # OCP nötig für STEP + Mock-Generierung
python -m pytest tests/ -q                 # komplette Suite inkl. E2E (~6 min)
python -m drawing_checker.app --check-rules            # YAML-Wissenspakete validieren
python -m drawing_checker.app --list-rules             # Regelkatalog je Profil
python -m drawing_checker.app --sap-import-vbs x.vbs   # Mitschnitt -> Ablauf
python -m drawing_checker.app --sap-dry-run 10473215   # Ablauf ohne SAP prüfen
python -m drawing_checker.app --ocr-check [x.pdf]      # OCR prüfen/vorführen
python -m drawing_checker.app --headless --mock mockdata/out \
    --excel mockdata/out/Materialliste_Mock.xlsx --column C
QT_QPA_PLATFORM=offscreen python -m drawing_checker.app --mock mockdata/out  # GUI headless

python -m mockdata bauen                   # Mockpakete nach mockdata/out/
python -m mockdata quellen                 # Kalibrierzeichnungen auspacken
python -m mockdata fehler <quelle> <ziel>  # Referenz- und Fehlerpakete

python -m tools.messen ocr                 # OCR-Güte messen
python -m tools.messen langlauf --count 200   # Dauerlauf: Speicher/Platte
python -m tools.messen kalibrier <ordner>     # Fehlalarme vs. Treffer
python -m tools.messen normen <csv> <yaml>    # Normstatus importieren

python -m tools.paket                      # ZIP + Einzeldatei bauen und prüfen
python -m tools.paket --nur bat            # nur dist/DrawingChecker_Setup.bat
```

## Architektur

Alle Module liegen flach in `drawing_checker/`:

| Modul | Inhalt |
|---|---|
| `kern.py` | Datenmodelle, Paketzugriff, Laufzustand (Resume), Haushalt |
| `ablauf.py` | Orchestrator: je Materialnummer, blockweise, abbrechbar |
| `zeichnung.py` | PDF-Textlayer/Rendering, Maßextraktion, Änderungsdatum, FCF |
| `ocr.py` | OCR und ihre Selbstprüfung |
| `regeln.py` | Regelmechanik, Profile, Validierung der YAMLs |
| `pruef_zeichnung.py` | Vollständigkeit, Schriftfeld, Sprache, Maßstab, Verfahren |
| `pruef_bemassung.py` | Maße, Toleranzen, GPS |
| `pruef_werkstoff.py` | Werkstoff, Verfahren, Gewicht, Beschaffung |
| `pruef_geometrie.py` | STEP-Abgleich, Silhouettenprojektion (alles OpenCascade) |
| `bericht.py` | Annotation, Excel-Rückschrieb, HTML-Bericht |
| `gui.py` | Fenster (PySide6) |
| `sap_ablauf.py` | .vbs-Mitschnitt einlesen und abspielen |
| `sap_sitzung.py` | Sitzung, Fenstergrenze, Popups, Download, Wächter, Diagnose |
| `sap_ymatdocs.py` | Adapter-Schnittstelle, echter Weg, Mock, Testsitzung |
| `sap_cli.py` | Kommandozeilenwerkzeuge rund um SAP |

Wichtig dabei:

- **SAP wird nicht programmiert, sondern aufgezeichnet.** `sap_ablauf.py`
  liest den .vbs-Mitschnitt und spielt ihn ab (generische `call`/`set_prop`
  decken auch ALV-Grid-Methoden ab); `sap_ymatdocs.py` klammert
  Download-Überwachung und Statusauswertung darum. Ablaufdatei:
  `regeln/ymatdocs_flow.yaml`. Die nachgebaute Sitzung in
  `sap_ymatdocs.py` deckt Tests und `--sap-dry-run` ab.
  Checkliste für den Durchstich: README.md, Abschnitt „SAP-Durchstich".
- **Wissen gehört in `rules/*.yaml`** (profiles, materials, norms,
  beschaffung) – NIE fachliche Listen im Code hartkodieren. YAML erweitern
  und `--check-rules` laufen lassen. Externe Overlays: Ordner `regeln/`
  neben der .exe bzw. `DRAWING_CHECKER_RULES`.
- **OCR** ist auf Zeichnungen getrimmt (400 dpi, Otsu, Deskew, PSM 11,
  90°-Durchgang für gedrehte Maßtexte, Wörterbücher aus, Nachkorrektur);
  jedes `Word` trägt eine Konfidenz, unsichere Zahlen werden kein Maß.
  Seitenweise: OCR nur für Seiten ohne Textlayer. Einstellungen über
  `DRAWING_CHECKER_OCR_*`, Güte messbar mit `tools.messen ocr`.
- **Ringschlüsse vermeiden**: `sap_sitzung` trägt die Adapter-Schnittstelle,
  `sap_ymatdocs` importiert nur in eine Richtung. Die `pruef_*`-Module
  greifen untereinander nur über träge Importe in Funktionen zu.

## Konventionen

- Jede neue Regel: Code (`GRUPPE.NAME`) in `rules/profiles.yaml` registrieren,
  Severity dort pflegen, mindestens 1 Positiv- + 1 Negativtest, Eintrag im
  Regelkatalog in README.md (ein Test erzwingt das).
- Unsicheres meldet `warning` („nicht nachweisbar/prüfen"), nie hart `error`.
- Findings mit `bbox` (PDF-Koordinaten) werden im Bild markiert.
- **Keine neuen Dateien, wo ein bestehendes Modul passt.** Ein Test in
  `tests/test_package.py` verbietet doppelt vergebene Namen auf Modulebene –
  daran ist beim Zusammenlegen ein verdeckter Regex aufgefallen.
- Gemeinsame Testhelfer (`make_ctx`, `codes`, `make_config`, `FONT`, `ECHT`,
  `FIXTURE`) stehen einmal in `tests/conftest.py`, nicht je Testdatei.
- Mockdaten sind Test-Fixtures (`tests/conftest.py` baut sie je Lauf);
  echte Kalibrierzeichnungen liegen als EIN Archiv `mockdata/echt_quellen.zip`
  (Lizenzen in `mockdata/echt_quellen/SOURCES.md`); `mockdata/daten.py`
  packt sie bei Bedarf nach `mockdata/.echt_quellen/` aus – nie wieder als
  Einzeldateien einchecken.
- Vor jedem Push: `python -m pytest tests/ -q` und `--check-rules`.
- Regeln werden an den 84 echten Fremdzeichnungen kalibriert, nicht an
  Musterzeichnungen: `python -m mockdata fehler` + `--headless` +
  `python -m tools.messen kalibrier`. Harte Meldungen auf den unveränderten
  Referenzen sind Fehlalarm-Verdacht.
- Speicher: OpenCascade und PyMuPDF geben nichts von selbst frei – nach
  großen Puffern `kern.release_memory()` aufrufen und mit
  `python -m tools.messen langlauf` gegenmessen.
- Übergabe an die nächste Sitzung: den Abschnitt „Übergabe" in README.md
  aktuell halten.
