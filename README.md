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

## Maßstabsbasierte Messung

Aus dem Schriftfeld-Maßstab und der gemessenen Ansichtsgröße errechnet der
Checker die Bauteilgröße **ohne jede Maßtext-Auswertung** – auf den
Mockzeichnungen exakt (420 × 70 mm für die Welle). Der Messwert steht in den
Excel-Vergleichswerten. Die daraus abgeleiteten Regeln `SCALE.MISMATCH`
(Zeichnung nicht maßstäblich) und `GEO.VIEW_SIZE` (Ansicht größer als das
Modell) werden **deaktiviert ausgeliefert**: Viele CAD-Systeme führen im
Schriftfeld nur den Blattmaßstab, während Detail- und Schnittansichten eigene
Maßstäbe haben. Wo eine einheitliche Zeichnungsnorm gilt, lohnt das
Einschalten in `profiles.yaml`.

## GD&T auf realen CAD-Zeichnungen

Toleranzrahmen werden von CAD-Systemen meist als **Vektorgrafik** gezeichnet:
Im Textlayer stehen nur Toleranzwert und Bezugsbuchstaben, das Symbol fehlt.
Das Tool erkennt die Rahmen deshalb geometrisch (`drawing/fcf.py`) und wertet
Wert und Bezüge aus. Die Art der Toleranz bleibt unbekannt – dafür meldet der
Checker `DOC.GDT_GRAPHIC` als Hinweis auf eine nötige Sichtprüfung, statt
stillschweigend nichts zu prüfen.

## Regelkatalog

Alle 98 Regeln mit Severity, Prüflogik und Normbezug sind in
[REGELKATALOG.md](REGELKATALOG.md) dokumentiert – die Grundlage für die
Abstimmung mit dem Fachbereich. Ein Test stellt sicher, dass neue Regeln
dort auftauchen.

## Gescannte Zeichnungen (OCR)

Alte Zeichnungen kommen als Scan ohne Textlayer aus dem Archiv. Der
OCR-Pfad ist auf technische Zeichnungen zugeschnitten und nicht auf
Fließtext:

| Maßnahme | Warum |
|---|---|
| 400 dpi, Otsu-Binarisierung | Maßtexte sind klein, Scans grau und verrauscht |
| Schräglagenkorrektur | Archivscans stehen selten gerade |
| PSM 11 („sparse text") | Zeichnungstext steht verstreut, nicht in Absätzen |
| Zweiter Durchgang auf dem um 90° gedrehten Bild | findet die Maße an senkrechten Maßlinien; übernommen wird daraus nur, was im Original hochkant steht |
| Wörterbücher aus | sonst „korrigiert" Tesseract `1.4301` oder `M12` kaputt |
| Nachkorrektur | `1O0` → `100`, `Ø`/`@` → `⌀`, Strichreste weg |
| Konfidenz je Wort | unsichere Zahlen werden **nicht** als Maß übernommen |

Gemischte Dokumente (Blatt 1 Scan, Blatt 2 aus dem CAD) werden seitenweise
behandelt – OCR läuft nur auf den Seiten ohne Textlayer.

Beruht die Prüfung auf OCR, meldet der Checker `DOC.OCR` mit Wortzahl und
mittlerer Erkennungsgüte, und ein Geometrie-Mismatch wird **nicht** als K.O.
gewertet, sondern als Prüfhinweis – ein falsch gelesenes Maß darf keine
Zeichnung sperren.

```bat
python -m drawing_checker.app --ocr-check                 # Installation prüfen
python -m drawing_checker.app --ocr-check zeichnung.pdf   # Leseprobe
```

Windows: Tesseract von der UB-Mannheim-Distribution installieren (Sprachen
**deu + eng** mitwählen), dann `pip install pytesseract`. Ohne Tesseract
läuft alles Übrige weiter; gescannte Zeichnungen melden dann `DOC.NO_TEXT`.

Stellschrauben ohne Codeänderung (Umgebungsvariablen):
`DRAWING_CHECKER_OCR_DPI`, `_MIN_CONF`, `_PSM`, `_ROTATIONS`, `_LANG`,
`_BINARIZE=0`, `_DESKEW=0`, `_FIX=0`, `_LINES=1`, `_DIM_CONF`, `_SHORT_CONF`.

Was die Abstimmung ergeben hat (jeweils am Messsatz gegengeprüft, nicht
geschätzt):

* **400 dpi** ist der beste Kompromiss – 300 dpi verliert Wörter, 600 dpi
  bringt keine besseren Maße und kostet ein Vielfaches an Rechenzeit.
* Der **90°-Durchgang** bringt die gedrehten Maßtexte, erzeugt aber ohne
  den Hochkant-Filter mehr erfundene als echte Maße. Mit Filter bleibt der
  Gewinn und die Fehlerquote sinkt (39 → 17 erfundene Maße).
* **Linienentfernung** (`_LINES=1`) bringt am sauberen Messsatz nichts und
  ist deshalb aus. Bei echten Archivscans, deren Maßlinien in die Schrift
  laufen, ist sie den Versuch wert – der Schalter ist dafür da.
* **`deu+eng`** bleibt Standard. Nur Englisch liefert an diesen (englischen)
  Zeichnungen weniger Fehlfunde; bei deutschen Zeichnungen ist das genau
  umgekehrt. Wer einen reinsprachigen Bestand hat, setzt `_LANG`.

Die Güte ist messbar: `python -m tools.ocr_bench mockdata/echt_quellen`
rastert echte Zeichnungen (deren Textlayer die Wahrheit liefert) und misst,
wie viel die OCR davon zurückgewinnt. Stand der Abstimmung, gemessen an
neun echten Zeichnungen als 200-dpi-Scan mit Rauschen:

| | Wörter | Maß-Token | Maße gefunden | erfundene Maße | falsche Regelbefunde |
|---|---|---|---|---|---|
| vorher (Standard-Tesseract) | 70 % | 45 % | 43/153 | 10 | +11 |
| jetzt | **84 %** | **61 %** | **74/153** | 17 | **+9** |

Bei schlechten Vorlagen (150 dpi, 1,5° schief) senkt allein die
Schräglagenkorrektur die falschen Regelbefunde von 33 auf 20. Die
verbleibenden Fehlbefunde erscheinen dank der Herabstufung nur als
„Prüfen", nie als Fehler.

## Gewichtsprüfung

Die Gewichtsangabe wird auf zwei Wegen verifiziert:

1. **Mit STEP** (`GEO.MASS`): Modellvolumen × Werkstoffdichte gegen die
   Angabe im Schriftfeld. Weicht sie ab, nennt `MASS.DENSITY_HINT` zusätzlich
   den Werkstoff, zu dem die Angabe rechnerisch passen *würde* – der
   Klassiker beim kopierten Schriftfeld.
2. **Ohne STEP** (`MASS.IMPOSSIBLE`, `MASS.TOO_LIGHT`): Die Angabe wird gegen
   einen Hüllquader aus den größten Zeichnungsmaßen gerechnet. Ein Teil kann
   nicht schwerer sein als der volle Quader – das findet vertauschte
   Einheiten und verrutschte Kommas ohne jedes Modell.

Rohteil-/Bruttogewichte werden erkannt und dem Fertiggewicht nachgeordnet,
weil das STEP das fertige Teil beschreibt.

## Anleitungen

- **[ANLEITUNG.md](ANLEITUNG.md)** – Kurzanleitung für Anwender (zwei Seiten).
- **[SAP_DURCHSTICH.md](SAP_DURCHSTICH.md)** – Mitschnitt einlesen und
  Durchstich am Einsatztag.
- **[UEBERGABE.md](UEBERGABE.md)** – Stand, Umgebung und nächste Schritte
  für die Weiterarbeit an einem anderen Rechner.
- **[KNOWHOW.md](KNOWHOW.md)** – Fachwissen ohne Code einpflegen.
- **[REGELKATALOG.md](REGELKATALOG.md)** – alle 98 Regeln im Klartext.

## Kalibrierung an echten Zeichnungen

`mockdata/echt_quellen/` enthält **84 echte, frei lizenzierte
Fertigungszeichnungen** (28 mit STEP) aus OreSat (CERN-OHL-S v2) und
ShapeOko (CC BY-SA 3.0) – Frästeile, Blech, Guss, Baugruppen, in mm und in
Zoll, ISO- und ASME-Bemaßung. `mockdata/inject_errors.py` erzeugt daraus je
Zeichnung ein unverändertes Referenzpaket und eines mit gezielt
eingebautem Fehler; `tools/kalibrier_auswertung.py` stellt beides
gegenüber.

Der Nutzen ist messbar: Der Lauf über diesen Satz hat drei echte Schwächen
aufgedeckt, die an selbstgebauten Musterzeichnungen unsichtbar blieben –
ein zu gieriges Regex machte aus 21 Frästeilen „Schweißteile", der
Geometrieabgleich meldete K.O., wenn nur das Gesamtmaß auf dem Blatt
fehlte, und Allgemeintoleranzen im Freitext („Tolerance unless otherwise
noted: +/- 0.25mm") galten als nicht vorhanden. Harte Fehlmeldungen auf den
unveränderten Zeichnungen: **155 → 88**.

## Dauerlauf

`tools/langlauf.py` prüft, ob das Werkzeug stundenlang durchhält: es baut
beliebig viele Materialnummern aus Mockpaketen, lässt den normalen
Orchestrator darüberlaufen und misst Speicher, Plattenbedarf und Zeit je
Nummer.

```bash
python -m tools.langlauf --count 200
```

Damit wurden zwei echte Speicherlecks gefunden (der STEP-Leser von
OpenCascade und der interne Zwischenspeicher von PyMuPDF) – vorher wuchs
der Prozess um rund 12 MB je Materialnummer, jetzt um 0,04 MB. Während des
Laufs werden entpackte Pakete nach der Prüfung gelöscht und der freie
Plattenplatz überwacht; wird es eng, hält der Lauf geordnet an und ist
fortsetzbar.

## Regelkatalog anpassen

`drawing_checker/rules/profiles.yaml` – Regeln je Materialgruppe
(default/guss/schweiss) an-/abschalten, Severities und Toleranzbänder für
den Geometrieabgleich ändern. Profile erben per `inherit` voneinander.

## SAP-Anbindung (Durchstich am Einsatztag)

Der Transaktionsablauf wird **nicht programmiert, sondern aufgezeichnet**:
der .vbs-Mitschnitt aus SAP wird eingelesen, in einen abspielbaren Ablauf
übersetzt und mit Platzhaltern (`{material}`, `{target_dir}`, `{filename}`)
versehen. Vier Schritte:

```bat
python -m drawing_checker.app --sap-import-vbs ymatdocs.vbs   # 1. einlesen
python -m drawing_checker.app --sap-dry-run 10473215          # 2. ohne SAP prüfen
python -m drawing_checker.app --sap-test   10473215           # 3. echt, ein Material
python -m drawing_checker.app                                 # 4. Dauerlauf (GUI)
```

Weitere Werkzeuge: `--sap-show-flow` (gespeicherten Ablauf anzeigen),
`--sap-dump` (Elementbaum des aktuellen SAP-Bildes – liefert die
Element-IDs), `--sap-flow <yaml>` (abweichender Ablaufpfad).

Die vollständige Checkliste inklusive Aufzeichnung, Handkorrekturen am
YAML und Fehlerbehebung steht in
[SAP_DURCHSTICH.md](SAP_DURCHSTICH.md).

Noch offen, unabhängig vom Mitschnitt:

1. **Login klären**: SSO oder Benutzer/Passwort? Bei Passwort: Eintrag
   `drawing-checker/P11` im Windows Credential Manager anlegen
   (`SapWatchdog.store_credentials`), der Watchdog nutzt ihn beim
   automatischen Neustart.
2. **`SAPLOGON_PATH`** setzen, falls saplogon.exe nicht im Standardpfad
   liegt.
3. Nach dem Durchstich: Kalibrierung der Checks an echten Zeichnungen
   (Regel-Severities in `profiles.yaml`).
4. Auslieferung: `pyinstaller packaging/DrawingChecker.spec` (Windows;
   Wissenspakete werden mitgepackt, Anwender-Ergänzungen kommen in einen
   Ordner `regeln/` neben die .exe).

Weiteres Wissen einpflegen (Normen, Werkstoffe, Regeln) ohne Code: siehe
[KNOWHOW.md](KNOWHOW.md). Echte Kalibrier-Zeichnungen: siehe
[mockdata/echt_quellen/SOURCES.md](mockdata/echt_quellen/SOURCES.md).
