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
| 10473215 | Schweißkonsole | Fehler: Werkstoff 1.4305 trotz Schweißnähten (fachlicher Widerspruch), „feuerverzinkt“ auf Edelstahl, deutsche Anmerkungen, ISO 5817 ohne Gruppe; STEP passt |
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

## Geometrieprüfung im Detail

Der Abgleich Zeichnung ↔ STEP läuft über vier unabhängige Indizien, damit
eine falsch gespeicherte Konfiguration auch dann auffällt, wenn ein
Einzelkriterium unscharf ist:

1. **Hüllmaße** – größte Zeichnungsmaße vs. optimale Bounding-Box des
   Modells, plus Raumdiagonalen-Prüfung (K.O.-Kriterium).
2. **Masse** – Gewichtsangabe im Schriftfeld vs. STEP-Volumen × Dichte des
   erkannten Werkstoffs (Dichten stehen in `rules/materials.yaml`).
3. **Bohrbild** – explizite Mehrfachangaben („4×⌀18") vs. tatsächlich im
   Modell vorhandene Bohrungen; Bohrungen und Außenzylinder werden über
   Flächenorientierung und Achslage unterschieden und je Achse gruppiert.
4. **Konturprojektion** (s. u.) als bestätigende Stufe.

Zusätzlich erkennt der Checker zwei Fehlerursachen, die wie ein
Geometrie-Mismatch aussehen, aber eine andere Behebung brauchen:
**Zoll/mm-Verwechslung** beim STEP-Export (`GEO.UNIT_MISMATCH`, unterdrückt
dann den Maß-K.O.) und **Baugruppe statt Einzelteil** im Paket
(`GEO.ASSEMBLY`; sich berührende, nicht verschmolzene Körper werden davon
als `GEO.NOT_FUSED` unterschieden).

## Ausbaustufe Konturprojektion

Zusätzlich zum Maßabgleich projiziert das Tool das STEP-Modell aus den drei
Hauptachsenrichtungen als Silhouette (OpenCascade HLR) und vergleicht sie
rotations-/spiegelinvariant mit den aus dem PDF extrahierten Ansichten
(Vektorlinien, ISO-128-Linienbreitenfilter trennt Kontur- von Maßlinien).
Der Kontur-Score schärft das Urteil konservativ: Er bestätigt ein „unsicher“
(→ passt) bzw. stuft ein „passt“ bei klarem Widerspruch auf „unsicher“ herab –
ein „passt nicht“ des Maßabgleichs bleibt immer bestehen. Abschaltbar über
Regel `GEO.CONTOUR` in `profiles.yaml`; benötigt das OCC-Backend.

## GD&T auf realen CAD-Zeichnungen

Toleranzrahmen werden von CAD-Systemen meist als **Vektorgrafik** gezeichnet:
Im Textlayer stehen nur Toleranzwert und Bezugsbuchstaben, das Symbol fehlt.
Das Tool erkennt die Rahmen deshalb geometrisch (`drawing/fcf.py`) und wertet
Wert und Bezüge aus. Die Art der Toleranz bleibt unbekannt – dafür meldet der
Checker `DOC.GDT_GRAPHIC` als Hinweis auf eine nötige Sichtprüfung, statt
stillschweigend nichts zu prüfen.

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
5. Auslieferung: `pyinstaller packaging/DrawingChecker.spec` (Windows;
   Wissenspakete werden mitgepackt, Anwender-Ergänzungen kommen in einen
   Ordner `regeln/` neben die .exe).

Weiteres Wissen einpflegen (Normen, Werkstoffe, Regeln) ohne Code: siehe
[KNOWHOW.md](KNOWHOW.md). Echte Kalibrier-Zeichnungen: siehe
[mockdata/echt_quellen/SOURCES.md](mockdata/echt_quellen/SOURCES.md).
