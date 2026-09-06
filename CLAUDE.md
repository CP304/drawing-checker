# Drawing Checker – Hinweise für Claude-Sessions

Internes Windows-Tool: prüft technische Zeichnungen je SAP-Materialnummer
(YMATDOCS-ZIP mit PDF + optional STEP) auf Normverstöße, fachliche
Widersprüche und Geometrie-Mismatch. GUI für nicht-technische Anwender.
Sprache im Code/UI: Deutsch (Docstrings, Findings, Commit-Messages).

## Kommandos

```bash
pip install -e .[occ,dev]                  # OCP nötig für STEP + Mock-Generierung
python -m pytest tests/ -q                 # komplette Suite inkl. E2E (~1 min)
python -m mockdata.generate                # Mockpakete nach mockdata/out/
python -m drawing_checker.app --headless --mock mockdata/out \
    --excel mockdata/out/Materialliste_Mock.xlsx --column C
python -m drawing_checker.app --check-rules   # YAML-Wissenspakete validieren
python -m drawing_checker.app --sap-import-vbs x.vbs   # Mitschnitt -> Ablauf
python -m drawing_checker.app --sap-dry-run 10473215   # Ablauf ohne SAP prüfen
python -m drawing_checker.app --list-rules    # Regelkatalog je Profil
python -m drawing_checker.app --ocr-check [x.pdf]  # OCR prüfen/vorführen
python -m tools.ocr_bench mockdata/echt_quellen    # OCR-Güte messen
QT_QPA_PLATFORM=offscreen python -m drawing_checker.app --mock mockdata/out  # GUI headless
```

## Architektur (Kurzfassung)

- `core/orchestrator.py` – Ablauf je Materialnummer, Resume-Zustand
  (`core/state.py`), Retries mit SAP-Recovery; erzeugt am Laufende
  HTML-Bericht, findings.csv und Excel-Zusammenfassung.
- `sap/` – Adapter-Interface. Der Transaktionsablauf wird NICHT
  programmiert: `vbs_parser.py` liest den .vbs-Mitschnitt, `script_flow.py`
  spielt ihn ab (generische `call`/`set_prop`-Schritte decken auch
  ALV-Grid-Methoden ab), `ymatdocs.py` klammert Download-Überwachung und
  Statusauswertung darum. Ablauf-Datei: `regeln/ymatdocs_flow.yaml`.
  `fake_session.py` simuliert SAP für Tests und `--sap-dry-run`;
  `mock.py` liefert ZIPs aus einem Ordner und kann Abstürze simulieren.
  Checkliste für den Durchstich: SAP_DURCHSTICH.md.
- `drawing/` – PyMuPDF-Textlayer/Rendering, Maßextraktion, Änderungsdatum.
  `ocr.py` ist auf Zeichnungen getrimmt (400 dpi, Otsu, Deskew, PSM 11,
  90°-Durchgang für gedrehte Maßtexte, Wörterbücher aus, Nachkorrektur);
  jedes `Word` trägt eine Konfidenz, unsichere Zahlen werden kein Maß.
  Seitenweise: OCR nur für Seiten ohne Textlayer. Einstellungen über
  `DRAWING_CHECKER_OCR_*`; Güte messbar mit `tools/ocr_bench.py`.
- `checks/` – Regelwerk. Wissen liegt in `rules/*.yaml` (profiles, materials,
  norms) – NIE fachliche Listen im Code hartkodieren; YAML erweitern und
  `--check-rules` laufen lassen. Externe Overlays: Ordner `regeln/` neben
  der .exe bzw. `DRAWING_CHECKER_RULES`.
- `checks/step_compare.py` + `checks/contour_projection.py` – Geometrie:
  Maßabgleich (OBB, Diagonale, Zylinder) + HLR-Silhouetten vs. Ansichten.
- `report/` – Annotation (Marker, Legende, Status-Stempel), Excel-Rückschrieb
  (Spalten per Name, nicht per Index!), HTML-Bericht.

## Konventionen

- Jede neue Regel: Code (`GRUPPE.NAME`) in `rules/profiles.yaml` registrieren,
  Severity dort pflegen, mindestens 1 Positiv- + 1 Negativtest.
- Unsicheres meldet `warning` („nicht nachweisbar/prüfen“), nie hart `error`.
- Findings mit `bbox` (PDF-Koordinaten) werden im Bild markiert.
- Mockdaten sind Test-Fixtures (`tests/conftest.py` baut sie je Lauf);
  echte Kalibrierzeichnungen liegen in `mockdata/echt_quellen/` (Lizenzen
  in SOURCES.md), Fehler-Injektion über `mockdata/inject_errors.py`.
- Vor jedem Push: `python -m pytest tests/ -q` und `--check-rules`.
