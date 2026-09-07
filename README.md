# Drawing Checker

Internes Tool zur automatisierten Prüfung technischer Zeichnungen je
Materialnummer: fachliche Prüfung der technischen Kommunikation nach
allgemeinen Normen (Sicht: internationaler Einkauf), Sprach-Check
(deutschsprachige Zeichnungen sind ein Finding) und Geometrieabgleich der
Zeichnung gegen das STEP-Modell (Erkennung falsch gespeicherter
Konfigurationen). Ergebnisse: annotiertes Zeichnungsbild je Materialnummer
plus Rückschrieb in eine Kopie der Input-Excel.

Konzept und Architektur: siehe [Übergabe](#übergabe--stand-und-nächste-schritte).

## Installation (Entwicklungsrechner)

```bash
pip install -e .[occ,dev]          # occ = exakte STEP-Analyse (empfohlen)
pip install -e .[sap]              # nur Windows: SAP GUI Scripting (pywin32)

**Auf dem Anwenderrechner (Windows) genügt ein Doppelklick auf
`Start.bat`.** Die Datei richtet beim ersten Start alles ein (virtuelle
Umgebung, alle Pakete) und startet danach das Programm; bei jedem weiteren
Start geht es sofort los. Sie prüft auch, ob Python und Tesseract vorhanden
sind, und sagt in Klartext, was zu tun ist, wenn nicht.

```bat
Start.bat                        Programm starten (richtet bei Bedarf ein)
Start.bat neu                    Umgebung verwerfen und neu aufbauen
Start.bat pruefen                Selbsttest laufen lassen
Start.bat --sap-import-vbs x.vbs Optionen an das Programm durchreichen
```

Zusatzpakete werden einzeln installiert: fällt eines aus (z. B. das große
3D-Paket hinter einem Proxy), läuft der Rest trotzdem, und die Einschränkung
wird benannt. Meldungen der Einrichtung landen in `logs/einrichtung.log`.
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
python -m mockdata bauen            # erzeugt mockdata/out/
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
Das Tool erkennt die Rahmen deshalb geometrisch (`zeichnung.py`) und wertet
Wert und Bezüge aus. Die Art der Toleranz bleibt unbekannt – dafür meldet der
Checker `DOC.GDT_GRAPHIC` als Hinweis auf eine nötige Sichtprüfung, statt
stillschweigend nichts zu prüfen.

## Regelkatalog

Alle 98 Regeln mit Severity, Prüflogik und Normbezug sind in
[Regelkatalog](#regelkatalog-alle-regeln-im-klartext) dokumentiert – die Grundlage für die
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

Die Güte ist messbar: `python -m tools.messen ocr` (nimmt ohne Angabe die
echten Kalibrierzeichnungen)
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

## Weitergabe an den Anwenderrechner

Der Zielrechner bekommt **eine einzige Datei**. Es gibt sie in zwei
Fassungen – beides ist *eine* Datei, die Wahl hängt nur am Virenscanner:

```bash
python -m tools.paket --nur bat        # dist/DrawingChecker_Setup.bat  (Doppelklick)
python -m tools.paket --nur zip        # dist/DrawingChecker.zip        (entpacken)
```

* **`dist/DrawingChecker_Setup.bat`** (rund 0,3 MB) trägt das Paket als Base64 in sich. Doppelklick: Sie entpackt sich
  in den Ordner `DrawingChecker` neben sich und startet die Einrichtung.
  Nichts wird in Windows installiert, nichts in der Registry geändert.
  Manche Virenscanner sehen selbstentpackende Batch-Dateien kritisch –
  dann die ZIP-Fassung nehmen.
* **`dist/DrawingChecker.zip`** (rund 0,2 MB) ist
  der unauffällige Weg: entpacken – es entsteht der Ordner
  `DrawingChecker` – und darin `Start.bat` doppelklicken.

Beide enthalten Programm, Wissenspakete, Startskript und Anleitungen (ohne
die Kalibrierzeichnungen) und prüfen sich beim Bauen selbst: entpacken,
`--check-rules` im entpackten Stand, Pflichtdateien vollständig. Alles
Weitere (virtuelle Umgebung, Pakete, Menü) macht `Start.bat`.

Der Ordner `dist/` ist **nicht** im Repository – die Auslieferung wird vor
der Weitergabe gebaut (`python -m tools.paket`, unter einer Minute), damit
nie ein alter Stand verteilt wird.

## Anleitungen

- **[LIESMICH.txt](LIESMICH.txt)** – Kurzanleitung für Anwender (zwei Seiten).
- **[SAP-Durchstich](#sap-durchstich--ablauf-für-den-einsatztag)** – Mitschnitt einlesen und
  Durchstich am Einsatztag.
- **[Übergabe](#übergabe--stand-und-nächste-schritte)** – Stand, Umgebung und nächste Schritte
  für die Weiterarbeit an einem anderen Rechner.
- **[Regelkatalog](#regelkatalog-alle-regeln-im-klartext)** – Fachwissen ohne Code einpflegen.
- **[Regelkatalog](#regelkatalog-alle-regeln-im-klartext)** – alle 98 Regeln im Klartext.

## Kalibrierung an echten Zeichnungen

`mockdata/echt_quellen.zip` enthält **84 echte, frei lizenzierte
Fertigungszeichnungen** (28 mit STEP) aus OreSat (CERN-OHL-S v2) und
ShapeOko (CC BY-SA 3.0) – Frästeile, Blech, Guss, Baugruppen, in mm und in
Zoll, ISO- und ASME-Bemaßung. Sie liegen als **ein** Archiv im Repository
(als über hundert Einzeldateien haben sie jede Dateiliste zugemüllt);
`python -m mockdata quellen` packt sie nach `mockdata/.echt_quellen/` aus,
die Werkzeuge tun das bei Bedarf von selbst. `python -m mockdata fehler`
erzeugt daraus je
Zeichnung ein unverändertes Referenzpaket und eines mit gezielt
eingebautem Fehler; `tools.messen kalibrier` stellt beides
gegenüber.

Der Nutzen ist messbar: Der Lauf über diesen Satz hat drei echte Schwächen
aufgedeckt, die an selbstgebauten Musterzeichnungen unsichtbar blieben –
ein zu gieriges Regex machte aus 21 Frästeilen „Schweißteile", der
Geometrieabgleich meldete K.O., wenn nur das Gesamtmaß auf dem Blatt
fehlte, und Allgemeintoleranzen im Freitext („Tolerance unless otherwise
noted: +/- 0.25mm") galten als nicht vorhanden. Harte Fehlmeldungen auf den
unveränderten Zeichnungen: **155 → 88**.

## Laufsteuerung: blockweise, abbrechbar, fortsetzbar

Der Lauf über eine ganze Materialgruppe dauert Stunden. Deshalb:

- **Fortlaufende Protokollierung:** Ergebnis-Excel und Lauf-Zustand werden
  nach *jeder* Materialnummer geschrieben.
- **Blockweise** (`batch_size`, Standard 25): nach jedem Block Zwischenstand
  sichern, HTML-Bericht neu schreiben, Speicher zurückgeben und die
  SAP-Session aufräumen (Dialoge schließen, zurück aufs Selektionsbild).
- **Abbrechen** wirkt sofort – der Abbruch greift zwischen den
  Ablaufschritten und im Warten auf den Download, nicht erst nach dessen
  Zeitablauf. Die angebrochene Materialnummer wird *nicht* als erledigt
  vermerkt.
- **Fortsetzen findet sich selbst:** Gesucht wird ein unfertiger Lauf zu
  *dieser* Datei, diesem Blatt und dieser Spalte – nicht einfach der
  neueste Ordner. Die GUI bietet es beim Start von selbst an.
- **SAP-Fenster begrenzt** (`max_sap_sessions`, Standard 5): Der Checker
  nutzt eine bestehende Session, öffnet höchstens eine eigene, schließt
  diese am Ende wieder und öffnet keine weitere, wenn die Grenze erreicht
  ist – er meldet es stattdessen.

## Dauerlauf

`tools.messen langlauf` prüft, ob das Werkzeug stundenlang durchhält: es baut
beliebig viele Materialnummern aus Mockpaketen, lässt den normalen
Orchestrator darüberlaufen und misst Speicher, Plattenbedarf und Zeit je
Nummer.

```bash
python -m tools.messen langlauf --count 200
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

**Der Mitschnitt ist die einzige Einrichtung.** Aus ihm kommen
Transaktionscode, Eingabefelder samt Werten, Download-Auslöser,
Datei-Dialog und – falls die Aufzeichnung mit `OpenConnection` beginnt –
auch das SAP-System. Die GUI hat dafür einen eigenen Knopf, zeigt an, ob
ein Ablauf vorhanden ist, meldet in Klartext zurück, was sie verstanden
hat, und verweigert den Start, solange nichts eingelesen wurde.

Weitere Werkzeuge: `--sap-show-flow` (gespeicherten Ablauf anzeigen),
`--sap-dump` (Elementbaum des aktuellen SAP-Bildes – liefert die
Element-IDs), `--sap-flow <yaml>` (abweichender Ablaufpfad).

Die vollständige Checkliste inklusive Aufzeichnung, Handkorrekturen am
YAML und Fehlerbehebung steht in
[SAP-Durchstich](#sap-durchstich--ablauf-für-den-einsatztag).

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
[Regelkatalog](#regelkatalog-alle-regeln-im-klartext). Echte Kalibrier-Zeichnungen: siehe
[mockdata/echt_quellen/SOURCES.md](mockdata/echt_quellen/SOURCES.md)
(die Zeichnungen selbst: `mockdata/echt_quellen.zip`).


---

# SAP-Durchstich – Ablauf für den Einsatztag

Ziel: Von der Aufzeichnung der Transaktion YMATDOCS bis zum laufenden
Dauerlauf in vier Schritten. Alles außer Schritt 0 ist bereits gebaut und
getestet – am Einsatztag ist nur der echte Mitschnitt einzusetzen.

Grundgedanke: **Es wird nichts abgetippt.** Der Mitschnitt (.vbs) wird
eingelesen, in einen abspielbaren Ablauf (`ymatdocs_flow.yaml`) übersetzt
und mit Platzhaltern versehen. Damit funktioniert derselbe Ablauf für jede
Materialnummer, und ein abweichendes Selektionsbild braucht keine
Codeänderung.

---

### 0. Mitschnitt erzeugen (in SAP, einmalig)

1. SAP GUI → *Optionen → Barrierefreiheit & Skripting → Skripting*:
   „Skripting aktivieren" an, „Hinweis bei Skriptanbindung" **aus**
   (sonst bestätigt der Anwender bei jedem Material einen Dialog).
2. In P11 anmelden.
3. Rechts unten in der Statusleiste: *Skript aufzeichnen und abspielen*
   → **Aufzeichnen**.
4. Die Transaktion **genau so** durchspielen, wie das Tool es tun soll:
   - `/nYMATDOCS` eingeben,
   - Materialnummer eintragen (eine echte, mit Dokumenten!),
   - übrige Selektionsfelder wie im Regelbetrieb füllen (Werk, Kennzeichen
     „mit STEP" …),
   - ausführen (F8),
   - das ZIP herunterladen (Toolbar-Knopf / Menü),
   - im Datei-Dialog Ordner + Dateiname eintragen und speichern,
   - zurück auf das Selektionsbild (F3 / grüner Pfeil) – **wichtig**, damit
     der nächste Durchlauf am selben Bild startet.
5. Aufzeichnung stoppen. Die .vbs liegt standardmäßig unter
   `%USERPROFILE%\Documents\SAP\SAP GUI\`.

> Tipp: Zusätzlich eine zweite Aufzeichnung mit einer Materialnummer
> **ohne** Dokumente machen. Daraus lässt sich der genaue Meldungstext
> ablesen, den das Tool als „nicht vorhanden" erkennen soll
> (`_looks_like_not_found` in `sap_ymatdocs.py`).

---

### 1. Mitschnitt einlesen

```bat
python -m drawing_checker.app --sap-import-vbs "C:\...\ymatdocs.vbs"
```

Ausgabe: der erkannte Ablauf in Klartext. Zu prüfen ist:

- **Transaktion** = YMATDOCS,
- **Materialnummer-Feld** erkannt (bei Select-Options bekommen LOW und
  HIGH beide `{material}`),
- der Schritt mit `<== DOWNLOAD` ist wirklich der Download-Auslöser,
- Datei-Dialog-Felder stehen auf `{target_dir}` / `{filename}`.

Gespeichert wird nach `regeln\ymatdocs_flow.yaml` (neben der .exe). Die
Datei ist **von Hand nachbesserbar** – reines YAML, ein Schritt pro
Eintrag. Nachträglich ansehen: `--sap-show-flow`.

Häufige Handkorrekturen:

| Problem | Korrektur im YAML |
|---|---|
| Materialnummer nicht erkannt | beim richtigen Schritt `value: '{material}'` setzen, oben `material_field:` eintragen |
| Falscher Download-Schritt markiert | `download_step_index:` auf den 0-basierten Index setzen |
| Schritt darf auch fehlen dürfen | `optional: true` ergänzen |
| Bild braucht Zeit | Schritt `- action: sleep` mit `value: 2` einfügen |

### 2. Trockenlauf (ohne SAP)

```bat
python -m drawing_checker.app --sap-dry-run 10473215
```

Spielt den Ablauf gegen eine simulierte Session ab und beantwortet:
Werden alle Platzhalter aufgelöst? Landet die Materialnummer in einem
Feld? Öffnet der Auslöser den Datei-Dialog, und entsteht danach die Datei
am erwarteten Ort? Rückgabewert 0 = in Ordnung.

### 3. Einzeltest gegen echtes SAP

```bat
python -m drawing_checker.app --sap-test 10473215
```

Verbindet sich mit P11 (bestehende Anmeldung wird genutzt), führt den
Ablauf einmal aus und legt das Paket unter `sap_test\` ab. Danach wird der
ZIP-Inhalt aufgelistet: wie viele PDF, wie viele STEP.

Schlägt es fehl, wird automatisch eine Diagnose geschrieben
(`sap_test\diagnose_<matnr>.txt`): Elementbaum des aktuellen Bildes,
Statuszeile, Fenstertitel. Daraus lassen sich die richtigen Element-IDs
ablesen. Zusätzlich jederzeit:

```bat
python -m drawing_checker.app --sap-dump
```

### 4. Dauerlauf

```bat
python -m drawing_checker.app            # GUI, Standardweg für Anwender
```

Ablauf-Datei wird automatisch gefunden (`regeln\ymatdocs_flow.yaml`);
abweichender Pfad über `--sap-flow`. Der Lauf ist wiederaufnehmbar:
Abbruch und Neustart setzen an der letzten offenen Materialnummer an.

---

### Was im Dauerlauf automatisch abgefangen wird

| Situation | Verhalten |
|---|---|
| Unerwarteter Dialog (Info, „überschreiben?") | wird bestätigt |
| Druck-/Löschdialog | wird **abgebrochen**, nie bestätigt |
| Mehrfachanmeldung | bestehende Sitzung fortsetzen |
| Datei-Dialog des Downloads | bleibt stehen – ihn bedient der Ablauf selbst |
| SAP hängt (Busy) | Warten bis 120 s je Schritt |
| SAP abgestürzt / Session tot | Watchdog startet SAP Logon neu, meldet in P11 an, Material wird wiederholt |
| Material ohne Dokumente | Zeile als „übersprungen" markiert, kein Fehler |
| Download landet woanders | mehrere Ordner werden überwacht (Zielordner, Downloads, SAP-Arbeitsverzeichnis, TEMP); die Datei wird an den Zielort verschoben |
| Download unvollständig | es wird gewartet, bis die Dateigröße stabil ist |
| Kein Download nach 180 s | Materialnummer gilt als fehlgeschlagen, Lauf geht weiter |

### Wenn etwas klemmt

- **„Element … nicht gefunden"** → Bild sieht anders aus als bei der
  Aufzeichnung. `--sap-dump` zeigt das aktuelle Bild; ID im YAML
  korrigieren oder Schritt `optional: true` setzen.
- **Ablauf hängt am Datei-Dialog** → prüfen, ob der Dialog wirklich
  `wnd[1]` ist (bei manchen Downloads `wnd[2]`); IDs im YAML anpassen.
- **Kein Download erkannt, obwohl die Datei da ist** → Ordner in
  `sap_sitzung.py::default_watch_dirs` ergänzen oder im Datei-Dialog den
  Zielordner erzwingen (`{target_dir}`).
- **Scripting-Hinweisdialog erscheint bei jedem Aufruf** → SAP-GUI-Option
  aus Schritt 0.2 abschalten.
- **„pywin32 fehlt"** → `pip install pywin32` (nur Windows).

### Aufbau der SAP-Schicht (zum Nachlesen)

| Datei | Aufgabe |
|---|---|
| `sap_ablauf.py` (Parser) | .vbs → Ablauf, erkennt Transaktion, Materialfeld, Dialogfelder, Download-Auslöser |
| `sap_ablauf.py` (Player) | Ablaufmodell + Player; `call`/`set_prop` bilden **jede** Scripting-Anweisung ab (auch ALV-Grid) |
| `sap_ymatdocs.py` | Ablauf je Materialnummer, Statusauswertung, Notnagel-Ablauf |
| `sap_sitzung.py` (Sitzung) | COM-Anbindung an P11, Wiederverwendung bestehender Sitzungen |
| `sap_sitzung.py` (Wächter) | Neustart von SAP Logon nach Absturz |
| `sap_sitzung.py` (Popups) | Dialogbehandlung |
| `sap_sitzung.py` (Download) | Erkennung der fertigen ZIP-Datei |
| `sap_sitzung.py` (Diagnose) | Elementbaum, Screenshot, Fehlerbericht |
| `sap_ymatdocs.py` (Testsitzung) | simulierte Session für Trockenlauf und Tests |


---

# Regelkatalog: alle Regeln im Klartext

Alle 98 Prüfregeln des Drawing Checkers – Grundlage für die Abstimmung mit
dem Fachbereich. Jede Regel ist über `drawing_checker/rules/profiles.yaml`
(bzw. ein eigenes Paket in `regeln/`) einzeln abschaltbar, und ihre Severity
ist frei einstellbar. Die aktuell aktiven Regeln zeigt
`drawing-checker --list-rules`.

**Severity-Konvention:** `K.O.` = Paket unbrauchbar/Geometrie passt nicht ·
`Fehler` = klare Beanstandung · `Prüfen` = nicht sicher entscheidbar,
Sichtprüfung nötig · `Hinweis` = informativ.

---

### Dokument und Paket (DOC)

| Code | Severity | Prüfung |
|---|---|---|
| `DOC.NO_PDF` | K.O. | Kein PDF im YMATDOCS-Paket – Zeichnung fehlt |
| `DOC.MULTI_PDF` | Hinweis | Mehrere PDFs im Paket; nennt das geprüfte |
| `DOC.NO_STEP` | Hinweis | Kein STEP – Geometrieprüfung entfällt |
| `DOC.NO_TEXT` | Prüfen | Kein Textlayer und kein OCR – textbasierte Checks entfallen |
| `DOC.OCR` | Prüfen | Prüfung basiert auf OCR (eingeschränkte Zuverlässigkeit) |
| `DOC.BALLOONS` | Prüfen | Stückliste vorhanden, aber keine Positionsballone erkennbar |
| `DOC.GDT_GRAPHIC` | Hinweis | Toleranzrahmen nur als Grafik – Toleranzart visuell prüfen |
| `DOC.SHEET_COUNT` | Fehler | „Blatt 1 von 3", geliefert wurde weniger – Zeichnung unvollständig |
| `DOC.ANNOTATIONS` | Prüfen | Nachträgliche PDF-Kommentare/Stempel/Freihandeinträge (Rotstift) |
| `DOC.DATE_FUTURE` | Prüfen | Datum auf der Zeichnung liegt in der Zukunft |
| `DOC.DECIMAL_MIXED` | Prüfen | Dezimalkomma und -punkt gemischt – international mehrdeutig |

### Schriftfeld (TB) – ISO 7200

| Code | Severity | Prüfung |
|---|---|---|
| `TB.DRAWNO` | Fehler | Zeichnungsnummer nicht nachweisbar |
| `TB.MATERIAL` | Fehler | Werkstoff-Feld nicht nachweisbar |
| `TB.SCALE` | Fehler | Maßstab nicht nachweisbar |
| `TB.WEIGHT` | Prüfen | Gewichtsangabe nicht nachweisbar |
| `TB.REVISION` | Prüfen | Änderungsindex/Revision nicht nachweisbar |
| `TB.APPROVAL` | Prüfen | Prüf-/Freigabevermerk nicht nachweisbar |

Suchbegriffe je Feld sind in `profiles.yaml` als `keywords` gepflegt und
zweisprachig (inkl. ASME-Schreibweisen wie „DWG. NO.").

### Toleranzgrundlagen (GT)

| Code | Severity | Prüfung |
|---|---|---|
| `GT.GENERAL_TOL` | Fehler | Keine Allgemeintoleranz (ISO 2768/22081 oder ASME-Toleranzblock); auch „ISO 2768 ohne Toleranzklasse" |
| `GT.PRINCIPLE` | Prüfen | Tolerierungsgrundsatz fehlt (ISO 8015 bzw. ASME Y14.5) |

### Form- und Lagetolerierung (GPS)

| Code | Severity | Prüfung | Norm |
|---|---|---|---|
| `GPS.DATUM` | Fehler | Lagetoleranz verwendet, kein Bezug erkennbar | ISO 1101 |
| `GPS.DATUM_UNDEFINED` | Fehler | Toleranzrahmen verweist auf nicht definierte Bezüge | ISO 5459 |
| `GPS.DATUM_UNUSED` | Prüfen | Bezug definiert, aber nie verwendet | – |
| `GPS.FORM_WITH_DATUM` | Fehler | Formtoleranz **mit** Bezug = Widerspruch | ISO 1101 |
| `GPS.ZONE_NO_DATUM` | Fehler | ⌀-Toleranzzone ohne Bezug (nur Lagetoleranzen haben ⌀-Zonen) | ISO 1101 |
| `GPS.ENVELOPE` | Prüfen | Enge Passung ohne Hüllbedingung Ⓔ und ohne Formtoleranz | ISO 8015 |
| `GPS.POSITION_NO_TED` | Prüfen | Positionstoleranz ohne theoretisch genaue Maße | ISO 5458 |
| `GPS.MOD_ON_FORM` | Fehler | Materialbedingung Ⓜ/Ⓛ an einer Formtoleranz | ISO 2692 |
| `GPS.DEPRECATED_SYMBOL` | Prüfen | Koaxialität ◎ / Symmetrie ⌯ (in ASME Y14.5-2018 gestrichen) | – |

`GPS.ENVELOPE` ist der in der Praxis teuerste Fall: Nach dem
Unabhängigkeitsprinzip begrenzt „⌀20 H7" nur das lokale Zweipunktmaß – die
Bohrung darf unrund oder krumm sein, solange die Messpunkte stimmen.

### Oberfläche und Kanten (SURF)

| Code | Severity | Prüfung |
|---|---|---|
| `SURF.ROUGHNESS` | Prüfen | Keine Oberflächenangabe (Ra/Rz, ISO 21920/1302 oder Freitext) |
| `SURF.EDGES` | Prüfen | Kein Kantenzustand (ISO 13715 oder „Kanten gebrochen") |
| `SURF.UNREALISTIC` | Fehler | Rauheit feiner als das genannte Verfahren liefert (z. B. Ra 0,8 auf Gussfläche) |
| `SURF.UNREALISTIC_MINOR` | Prüfen | Ra < 0,4 µm ohne Angabe eines Feinbearbeitungsverfahrens |
| `SURF.TOL_MISMATCH` | Prüfen | Rauheit zu grob für die engste Maßtoleranz (Rz > 50 % der Toleranzbreite) – das Maß ist so nicht reproduzierbar messbar |

### Darstellung und Bemaßung (VIEW, DIM, SCALE, THRD)

| Code | Severity | Prüfung |
|---|---|---|
| `VIEW.PROJECTION` | Prüfen | Projektionsmethode nicht nachweisbar (bei ASME Y14.5 impliziert) |
| `VIEW.UNIT` | Prüfen | Einheit nicht deklariert |
| `DIM.CHAIN` | Prüfen | Geschlossene Maßkette: Teilmaße auf einer Maßlinie summieren sich zum ebenfalls tolerierten Gesamtmaß |
| `DIM.TOL_ORDER` | Fehler | Grenzabmaße vertauscht (oberes Abmaß kleiner als unteres) – leeres Toleranzfeld, nicht fertigbar |
| `DIM.BASIC_TOL` | Fehler | Theoretisch genaues Maß (eingerahmt) zusätzlich toleriert – Widerspruch zu ISO 1101 |
| `THRD.DEPTH` | Fehler | Gewinde tiefer gefordert als die zugehörige Kernbohrung – nicht herstellbar |
| `THRD.SHORT` | Prüfen | Einschraubtiefe unter 1×D (Stahl) bzw. 1,5×D (Aluminium) – das Gewinde reißt vor der Schraube aus (VDI 2230) |
| `THRD.FIT_CLASS` | Fehler | Gewinde mit Passungsklasse bemaßt („M12 H7" statt 6H/6g, ISO 965) |
| `SCALE.MISMATCH` | *(aus)* | Gemessene Ansicht überschreitet das größte eingetragene Maß |

### Masse-Plausibilität ohne STEP (MASS)

| Code | Severity | Prüfung |
|---|---|---|
| `MASS.IMPOSSIBLE` | Fehler | Gewichtsangabe schwerer als ein **voller** Quader der Hüllmaße – physikalisch unmöglich; nennt den Faktor (1000 ≈ g/kg vertauscht) |
| `MASS.TOO_LIGHT` | Prüfen | Füllgrad unter 1 % des Hüllquaders – bei Blech/Schweißrahmen normal, sonst verdächtig |
| `MASS.DENSITY_HINT` | Prüfen | Mit STEP: Gewicht/Modellvolumen ergibt die Dichte eines **anderen** Werkstoffs (kopiertes Schriftfeld) |

Die Hüllmaße stammen aus den drei größten Zeichnungsmaßen und sind eher zu
groß geschätzt – das Urteil „unmöglich" ist damit auf der sicheren Seite.
Gewichtsangaben mit „Rohteil"/„brutto" werden erkannt und dem Fertiggewicht
nachgeordnet.

### Fertigungsgerechtigkeit (MFG)

| Code | Severity | Prüfung |
|---|---|---|
| `MFG.TIGHT_TOL` | Prüfen | Sehr enge Toleranz (IT ≤ 5 bzw. < 10 µm) – stärkster Kostentreiber der Zerspanung |
| `MFG.DEEP_HOLE` | Prüfen | Bohrung mit Tiefe/Durchmesser > 5 (Tiefbohren nötig) |
| `MFG.SHARP_CORNER` | Prüfen | „R0"/scharfe Innenecke – mit Fräser nicht herstellbar |

### Internationale Beschaffung (PUR)

| Code | Severity | Prüfung |
|---|---|---|
| `PUR.VAGUE_SPEC` | Prüfen | Unbestimmte Angaben („ca. 20", „nach Absprache", „sauber entgraten", „TBD") – nicht kalkulierbar, nicht abnahmefähig |
| `PUR.INTERNAL_NORM` | Prüfen | Verweis auf Werk-/Konzernnormen (WN, HN, TL, MBN, VW, DBL …), die ein externer Lieferant nicht beziehen kann |
| `PUR.STOCK_SIZE` | Hinweis | Blechdicke/Rundmaterial außerhalb der Vorzugsmaße – Sondermaß mit Preis- und Lieferzeitfolge |

Formulierungen, Hausnorm-Kürzel und Vorzugsmaße stehen in
`rules/beschaffung.yaml` und sind ohne Codeänderung erweiterbar.

### Sprache (LANG)

| Code | Severity | Prüfung |
|---|---|---|
| `LANG.GERMAN` | Fehler | Rein deutschsprachige Beschriftung (zweisprachig ist ok) – Sicht des internationalen Einkaufs |

### Werkstoff und fachliche Widersprüche (MAT, COAT, PROC, WELD, NORM)

| Code | Severity | Prüfung |
|---|---|---|
| `MAT.MISSING` | Fehler | Kein Werkstoff angegeben |
| `MAT.UNKNOWN` | Prüfen | Werkstoff-Feld vorhanden, Bezeichnung nicht erkannt (Datenbank erweitern) |
| `MAT.WELD_CONFLICT` | Fehler | Nicht schweißgeeigneter Werkstoff + Schweißangaben (1.4305, GJL, 7075, Automatenstähle) |
| `MAT.WELD_LIMITED` | Prüfen | Nur bedingt schweißgeeignet (42CrMo4, C45, GJS) |
| `MAT.HT_CONFLICT` | Fehler | Wärmebehandlung passt nicht zum Werkstoff (S235 „gehärtet") |
| `MAT.COATING_CONFLICT` | Fehler | Verzinken auf Edelstahl/Alu, Eloxieren auf Nicht-Alu, Brünieren auf Nichtstahl |
| `MAT.ANODIZE_ALLOY` | Fehler | Alu-Legierung zum Eloxieren ungeeignet (AlSi-Guss, 2007/2024) |
| `MAT.ANODIZE_LIMITED` | Prüfen | Nur bedingt eloxierbar (7075) |
| `MAT.CAST_CONFLICT` | Prüfen | Gusskontext ohne Gusswerkstoff |
| `COAT.FIT` | Prüfen | Beschichtung + Passung/Gewinde ohne Freihalte-/Nacharbeitsvermerk |
| `COAT.EMBRITTLEMENT` | Fehler | Galvanische Beschichtung an hochfestem Bauteil (≥ 1000 MPa / 320 HV / 32 HRC / Klasse 10.9) ohne geforderte Wasserstoffarmglühung nach EN ISO 4042 |
| `PROC.STUD_ON_ZINC` | Fehler | Schweißbolzen auf feuerverzinktem Teil |
| `PROC.WELD_ZINC_ORDER` | Prüfen | Schweißen und Verzinken ohne Reihenfolgeangabe |
| `WELD.MIXED` | Fehler | Aluminium + Stahl geschweißt |
| `WELD.MIXED_FILLER` | Prüfen | Schwarz-Weiß-Verbindung ohne Zusatzwerkstoff (309L) |
| `NORM.MATERIAL_MISMATCH` | Fehler | ISO 5817 bei Aluminium (statt ISO 10042) und umgekehrt |
| `NORM.OBSOLETE` | Prüfen | Zurückgezogene/ersetzte Norm (23 Einträge, per CSV erweiterbar) |
| `NORM.WELD_GENTOL` | Prüfen | Schweißkonstruktion nur mit ISO 2768, ISO 13920 fehlt |
| `CONS.MATNO` | Prüfen | Materialnummer der Anfrage auf der Zeichnung nicht gefunden |

### Verfahrensspezifische Vollständigkeit (WELD, CAST, SHEET, HT)

| Code | Severity | Prüfung | Norm |
|---|---|---|---|
| `WELD.QUALITY` | Fehler | Schweißteil ohne Bewertungsgruppe | ISO 5817 |
| `WELD.NO_SIZE` | Fehler | Schweißangaben ohne Nahtdicke (a-/z-Maß) | ISO 2553 |
| `WELD.AZ_MIXED` | Prüfen | a- und z-Maße gemischt (Faktor √2 ≈ 29 % Unterschied) | ISO 2553 |
| `WELD.NO_PREP` | Prüfen | Stumpf-/Fugennaht ohne Nahtvorbereitung | ISO 9692 |
| `CAST.TOL` | Fehler | Gussteil ohne Gusstoleranz | ISO 8062 |
| `CAST.NO_DRAFT` | Prüfen | Gussteil ohne Formschrägen | DIN EN 12890 |
| `CAST.NO_RMA` | Prüfen | Bearbeitetes Gussteil ohne Bearbeitungszugabe | ISO 8062-3 |
| `SHEET.NO_THICK` | Fehler | Blech-/Biegeteil ohne Blechdicke | – |
| `SHEET.NO_RADIUS` | Prüfen | Abkantung ohne Biegeradius | – |
| `HT.NO_HARDNESS` | Prüfen | Wärmebehandlung ohne Härtewert (entfällt bei +QT/+N und Festigkeitsangabe) | DIN 6773 |
| `HT.NO_DEPTH` | Prüfen | Randschichthärten ohne Einhärtetiefe (Eht/CHD/NHD) | DIN 6773 |
| `HT.HARDNESS_LIMIT` | Fehler | Härteforderung über dem Werkstoffmaximum (z. B. 64 HRC auf C45) | – |

### Geometrieabgleich mit STEP (GEO)

| Code | Severity | Prüfung |
|---|---|---|
| `GEO.MISMATCH` | K.O. | Hüllmaße passen nicht (Maß größer als Raumdiagonale oder Hauptmaß weit daneben) |
| `GEO.UNCERTAIN` | Prüfen | Nicht sicher bewertbar – manuelle Prüfung |
| `GEO.NO_DIMS` | Prüfen | Keine Maße extrahierbar, Abgleich nur eingeschränkt |
| `GEO.MASS` | Fehler | Gewichtsangabe vs. Volumen × Werkstoffdichte weicht stark ab |
| `GEO.MASS_MINOR` | Prüfen | Moderate Massenabweichung (bei Guss/Schweiß normal) |
| `GEO.HOLE_COUNT` | Fehler | „4×⌀18" der Zeichnung fehlt im Modell |
| `GEO.HOLE_COUNT_MINOR` | Prüfen | Bohrbild teilweise vorhanden |
| `GEO.THREAD` | Prüfen | Gewinde ohne passendes Kernloch im Modell |
| `GEO.UNIT_MISMATCH` | Fehler | Zoll/mm-Verwechslung beim STEP-Export (Faktor 25,4) |
| `GEO.ASSEMBLY` | Fehler | Räumlich getrennte Körper, aber Einzelteilzeichnung |
| `GEO.ASSEMBLY_MINOR` | Prüfen | Stückliste vorhanden, Modell hat nur einen Körper |
| `GEO.NOT_FUSED` | Hinweis | Sich berührende, nicht verschmolzene Körper |
| `GEO.CONTOUR` | Prüfen | Konturprojektion (bestätigt bzw. entkräftet das Maß-Urteil) |
| `GEO.MIRROR` | Fehler | Die Ansichten passen besser zum **gespiegelten** Modell – falsche Hand gespeichert. Hüllmaße, Volumen, Masse und Bohrbild sind bei gespiegelten Teilen identisch; nur die Kontur verrät den Fall |
| `GEO.VIEW_SIZE` | *(aus)* | Gemessene Ansicht größer als das Modell |

Der Geometrieabgleich stützt sich auf fünf unabhängige Indizien (Hüllmaße,
Masse, Bohrbild, Konturprojektion, Spiegelung) – siehe README.

**Richtung der Abweichung entscheidet über die Härte:** Ist ein bemaßtes Maß
*größer* als das Modell, kann das Teil es nicht enthalten – K.O. Ist
umgekehrt das *Modell* größer als jedes bemaßte Maß, fehlt meist nur das
Gesamtmaß auf dem Blatt (Maßkette, Folgeblatt); das gibt nur „Prüfen".
Am Kalibriersatz aus 84 echten Zeichnungen war das die Ursache für drei von
vier K.O.-Fehlurteilen. `SCALE.MISMATCH` und
`GEO.VIEW_SIZE` sind im Auslieferzustand deaktiviert, weil Blatt- und
Ansichtsmaßstab in vielen CAD-Systemen auseinanderfallen.

---

### Profile

| Profil | Besonderheit |
|---|---|
| `default` | Grundeinstellung für spanend gefertigte Teile |
| `guss` | Größere Geometrie- und Massetoleranzen (Rohteil vs. Fertigteil), `GEO.MISMATCH` nur als Warnung |
| `schweiss` | Größere Toleranzen wegen Verzug/Nahtaufbau, `WELD.QUALITY` als Fehler |

Eigene Profile je Materialgruppe legt man in `regeln/profiles_firma.yaml`
per `inherit` an – siehe [Regelkatalog](#regelkatalog-alle-regeln-im-klartext).

---

## Know-how einpflegen – ohne KI, ohne Programmierung

Das Prüfwissen des Tools liegt vollständig in **YAML-Wissenspaketen** unter
`drawing_checker/rules/`. Wer Fachwissen hat, erweitert Dateien – keinen Code.
Jede Datei `materials*.yaml` und `norms*.yaml` in dem Ordner wird automatisch
mitgeladen; Firmenpakete (z. B. `norms_firma.yaml`, `materials_firma.yaml`)
liegen neben den mitgelieferten und überstehen Updates des Tools.

### Manuell nachpflegen – so geht's

1. **Wo?** Beim installierten Tool (.exe) einen Ordner **`regeln/` neben die
   Anwendung** legen (alternativ beliebiger Ordner über die Umgebungsvariable
   `DRAWING_CHECKER_RULES`). Alles dort Abgelegte lädt zusätzlich zu den
   mitgelieferten Paketen; gleichnamige Profile/Regeln überschreiben die
   Mitgelieferten. Die mitgelieferten Dateien selbst nie anfassen – so
   überleben eigene Einträge jedes Tool-Update.
2. **Was?** Einfach eine Textdatei anlegen, z. B. `regeln/materials_firma.yaml`,
   `regeln/norms_firma.yaml` oder `regeln/profiles_firma.yaml` – Format wie in
   den mitgelieferten Dateien (dort sind alle Felder kommentiert; ein Eintrag
   ist eine Zeile, Editor genügt, kein Python nötig).
3. **Prüfen:** `drawing-checker --check-rules` validiert alle Pakete und
   meldet Probleme in Klartext mit Datei und Eintrag (leeres/falsches Feld,
   Regex-Tippfehler, unbekannte Kategorie/Severity, doppelte Namen). Die GUI
   macht dieselbe Prüfung beim Start und zeigt Funde als Warnung.
4. **Sicherheitsnetz:** Ein fehlerhafter Eintrag bricht nie den Prüflauf ab –
   er wird ignoriert und geloggt, der Rest des Pakets lädt normal.

### Die drei Wissensspeicher

| Datei | Inhalt | Wer pflegt |
|---|---|---|
| `rules/profiles.yaml` | Regeln je Materialgruppe: an/aus, Severity, Schlüsselwörter, Toleranzbänder für den Geometrieabgleich | Fachbereich |
| `rules/materials.yaml` | Werkstoffe: Erkennungsmuster + Eigenschaften (schweißgeeignet, härtbar, verzinkbar, eloxierbar, Guss) → speist die Widerspruchsprüfung | Fachbereich/Schweißaufsicht |
| `rules/norms.yaml` | Zurückgezogene/ersetzte Normen mit Hinweis auf den Nachfolger | Normenstelle |
| `rules/beschaffung.yaml` | Unbestimmte Formulierungen, nicht beziehbare Haus-/Konzernnormen, Vorzugsmaße für Halbzeuge | Einkauf/Arbeitsvorbereitung |

### Massenimport statt Handarbeit

1. **Normenverwaltung anzapfen (größter Hebel):** Nautos/Perinorm können
   Trefferlisten mit Status und Nachfolgedokument als CSV exportieren.
   `python -m tools.messen normen export.csv drawing_checker/rules/norms_firma.yaml`
   erzeugt daraus hunderte Prüfeinträge in einem Schritt.
2. **Firmennormen/Prüfkataloge:** Bestehende Prüf-Checklisten des Fachbereichs
   Zeile für Zeile in `profiles.yaml`-Regeln bzw. Schlüsselwortlisten gießen.
   Ein Eintrag = eine Zeile YAML.
3. **Werkstofffreigabelisten des Einkaufs:** Die intern freigegebenen
   Werkstoffe (inkl. Lieferanten-Alternativbezeichnungen) nach
   `materials_firma.yaml` übernehmen – dann erkennt das Tool auch exotische
   Hausbezeichnungen.
4. **Alte Prüfberichte als Regelquelle:** Jede wiederkehrende manuelle
   Beanstandung aus alten Prüfungen ist ein Regelkandidat. Faustregel: Was
   dreimal manuell beanstandet wurde, wird eine YAML-Regel.

### Qualitätssicherung beim Einpflegen (Golden Set)

- `mockdata/echt_quellen.zip` enthält 84 echte Zeichnungen (auspacken mit
  `python -m mockdata quellen`); `python -m mockdata fehler`
  erzeugt daraus Pakete mit dokumentierten Soll-Fehlern (`MANIFEST.txt`).
- Nach jeder Wissensänderung: `python -m pytest tests/ -q` und einen
  Kalibrierlauf über das Golden Set – neue Regeln dürfen die Referenzpakete
  (unveränderte Originale) nicht plötzlich rot färben.
- Regex-Tippfehler in den YAMLs fallen beim Start auf (Validierung beim Laden)
  und brechen den Lauf nicht stumm ab.

### Grenzen, die man kennen muss

- **GD&T-Symbole** liegen in vielen CAD-PDFs nicht im Textlayer (Grafik oder
  Symbolschrift). Der Checker erkennt Toleranzrahmen geometrisch und prüft
  Werte und Bezüge; die Toleranzart (Position, Ebenheit, Rundlauf …) meldet
  er als sichtprüfungspflichtig (`DOC.GDT_GRAPHIC`).
- **Theoretisch genaue Maße** (eingerahmt) sind im Textlayer oft nicht von
  normalen Maßen unterscheidbar – `GPS.POSITION_NO_TED` ist deshalb eine
  Warnung mit Sichtprüfungshinweis, kein harter Fehler.
- **Maßketten** werden nur gemeldet, wenn die Maße auf einer gemeinsamen
  Maßlinie nebeneinander liegen. Ohne diese räumliche Prüfung liefert die
  reine Zahlensuche auf maßreichen Zeichnungen Zufallstreffer.
- **Maßstabsprüfungen** (`SCALE.MISMATCH`, `GEO.VIEW_SIZE`) sind
  ausgeliefert deaktiviert, weil Blattmaßstab und Ansichtsmaßstab in vielen
  CAD-Systemen auseinanderfallen. Die gemessene Ansichtsgröße erscheint
  trotzdem in den Vergleichswerten.
- **Masseabgleich** setzt eine Gewichtsangabe im Schriftfeld und eine
  bekannte Werkstoffdichte voraus; Rohteilgewichte weichen bei Guss- und
  Schweißteilen systematisch ab (Toleranz je Profil einstellbar).

### Grundsätze

- **Konservativ formulieren:** Muster so eng, dass sie nur den gemeinten Fall
  treffen („2768" nur mit ISO davor). Lieber ein übersehener Fund als
  Fehlalarm-Rauschen – Rauschen zerstört das Vertrauen in die Triage.
- **Unsicheres ist gelb, nicht rot:** Was auf der Zeichnung nicht sicher
  entscheidbar ist, wird „Prüfen" (warning), niemals hart „Fehler".
- **Jede Regel hat einen Code** (z. B. `MAT.WELD_CONFLICT`) – der taucht in
  Excel und Bild auf und macht Beanstandungen diskutierbar/abschaltbar.


---

# Übergabe – Stand und nächste Schritte

Diese Datei ist für die **nächste Sitzung an einem anderen Rechner**
gedacht (Claude oder Mensch). Sie beantwortet: Was ist gebaut, was ist zu
tun, was muss man wissen, um nicht in dieselben Gruben zu fallen.

Stand: 06.09.2026, Branch `claude/drawing-validation-tool-inzji1`.

### 1. Was das Werkzeug heute kann

Vollständig gebaut und getestet (ohne SAP lauffähig über `--mock`):

- **98 Prüfregeln** in neun Gruppen (siehe Abschnitt „Regelkatalog“), Wissen in
  YAML unter `drawing_checker/rules/` – Werkstoffe, Normen, Beschaffung.
- **Geometrieabgleich** gegen STEP über fünf unabhängige Indizien:
  Hüllmaße, Masse (Volumen × Dichte), Bohrbild, Konturprojektion (HLR)
  und Spiegelung (falsche Hand).
- **Masse-Plausibilität auch ohne STEP** (Hüllquader × Dichte).
- **OCR für gescannte Zeichnungen**, auf Zeichnungen getrimmt und messbar
  (`tools.messen ocr`).
- **SAP-Anbindung ablaufgesteuert**: der .vbs-Mitschnitt wird eingelesen
  und abgespielt, nichts ist hartcodiert (Abschnitt „SAP-Durchstich“ weiter unten).
- **GUI** (PySide6) mit Fortschritt, Pause/Fortsetzen, Detailansicht;
  Ergebnisse in Excel, HTML-Bericht, findings.csv, annotierte Bilder.
- **Dauerlauf-Haushalt**: Pakete werden nach der Prüfung gelöscht,
  Plattenplatz überwacht, Speicher wird freigegeben.

### 2. Das Wichtigste zuerst: der SAP-Durchstich

**Ohne den .vbs-Mitschnitt der Transaktion YMATDOCS läuft nichts im
Echtbetrieb.** Die komplette Anleitung steht in **Abschnitt „SAP-Durchstich“ weiter unten** –
dort anfangen. Kurzform:

```bat
python -m drawing_checker.app --sap-import-vbs ymatdocs.vbs
python -m drawing_checker.app --sap-dry-run 10473215
python -m drawing_checker.app --sap-test   10473215
python -m drawing_checker.app                      # GUI-Dauerlauf
```

Bei Problemen: `--sap-dump` zeigt den Elementbaum des aktuellen SAP-Bildes;
ein fehlgeschlagener `--sap-test` schreibt automatisch eine Diagnose.

#### Nur der Mitschnitt

Alles, was das Werkzeug über die Transaktion weiß, kommt aus der `.vbs`:
Transaktionscode, Felder, Werte, Download-Auslöser, Datei-Dialog und (bei
`OpenConnection`) das SAP-System. `vbs_parser.uebernehmen()` bündelt
Einlesen + Speichern + Kurzbericht für GUI und CLI;
`vbs_parser.kurzbericht()` sagt, ob der Ablauf brauchbar ist
(Materialnummer-Feld UND Download-Schritt erkannt). Die GUI ruft
`_ablauf_uebernehmen()` (ohne Dialoge, damit prüfbar) und legt die
Meldungen nur darum herum.

### 3. Umgebung einrichten (neuer Rechner)

**Weitergabe:** Es gibt zwei Fassungen, beides *eine* Datei:

```bash
python -m tools.paket --nur bat     # dist/DrawingChecker_Setup.bat - Doppelklick,
                                # entpackt sich selbst und startet Start.bat
python -m tools.paket --nur zip     # dist/DrawingChecker.zip - entpacken, Start.bat
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
`python -m mockdata bauen` legt sie in `mockdata/out/` ab.

### 4. Wie hier gearbeitet wird (Konventionen, die zählen)

- **Sprache Deutsch** in Code, Docstrings, Findings, Commit-Messages.
- **Fachwissen gehört in YAML**, nicht in den Code. Neue Werkstoffe,
  Normen, Formulierungen in `drawing_checker/rules/*.yaml` ergänzen und
  `--check-rules` laufen lassen.
- **Jede neue Regel**: Code in `rules/profiles.yaml` registrieren,
  Severity dort pflegen, mindestens ein Positiv- und ein Negativtest, und
  im Regelkatalog dieses Dokuments eintragen (ein Test erzwingt das).
- **Unsicheres meldet „Prüfen", nie hart „Fehler".** Bei OCR-Grundlage
  wird jede Meldung automatisch heruntergestuft.
- **Vor jedem Push**: `python -m pytest tests/ -q` und `--check-rules`.

### 5. Womit Regeln kalibriert werden

`mockdata/echt_quellen.zip` enthält **84 echte, frei lizenzierte
Fertigungszeichnungen** (28 mit STEP) aus OreSat (CERN-OHL-S v2) und
ShapeOko (CC BY-SA 3.0) – Herkunft und Auswahlkriterien in
`mockdata/echt_quellen/SOURCES.md`. Sie liegen bewusst als **ein** Archiv im
Repository; `python -m mockdata quellen` packt sie nach
`mockdata/.echt_quellen/` aus (nicht im Repository), die Werkzeuge unten tun
das bei Bedarf von selbst. Bitte nicht wieder als Einzeldateien einchecken.

```bash
python -m mockdata fehler mockdata/echt_quellen /tmp/kal
python -m drawing_checker.app --headless --mock /tmp/kal \
    --excel /tmp/kal/Materialliste_Echt.xlsx --column C
python -m tools.messen kalibrier /tmp/kal
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

### 5b. Laufsteuerung (neu)

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

### 6. Messwerkzeuge

| Werkzeug | Frage, die es beantwortet |
|---|---|
| `python -m tools.messen langlauf --count 200` | Läuft das Tool stundenlang stabil? Speicher, Platte, Zeit je Materialnummer |
| `python -m tools.messen ocr` | Wie viel erkennt die OCR von einer gescannten Zeichnung wieder? |
| `python -m tools.messen kalibrier <ordner>` | Wie viele Fehlalarme produzieren die Regeln? |
| `python -m drawing_checker.app --list-rules` | Was ist je Profil aktiv? |

Die Langlaufmessung hat zwei echte Speicherlecks gefunden (OpenCascade-
Leser und der interne Zwischenspeicher von PyMuPDF). Beide sind behoben;
wer an `ocr.py`, `step_compare.py` oder `annotate.py` arbeitet, sollte die
Messung danach wiederholen.

### 7. Was als Nächstes ansteht (Priorität)

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

### 8. Stolpersteine, die schon Zeit gekostet haben

- **OCP heißt je nach Python-Fassung anders.** Python 3.10 bekommt
  cadquery-ocp 7.9 (die letzte dafür gebaute), 3.11+ bekommt 8.x. In 7.9
  fehlt `Bnd_Box.GetXMin()`; deshalb liest `step_compare._box_bounds()`
  über `CornerMin()/CornerMax()`. Wer OCP-Aufrufe ergänzt, prüft sie
  gegen BEIDE Fassungen – sonst läuft das Werkzeug auf dem Zielrechner
  nicht, obwohl hier alles grün ist.
- **OCP-Namen**: `TopoDS.Face` funktioniert in beiden Fassungen
  (`Face_s` gibt es nur in 7.9).
- **OpenCascade und PyMuPDF geben Speicher nicht von selbst frei** – siehe
  `kern.release_memory()`.
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

## Anhang: ursprüngliche Planung

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

### 1. Zielbild / Ablauf aus Anwendersicht

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

### 2. Architektur

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

#### Modulschnitt (Repo-Layout)

> Die ursprüngliche Planung sah sechs Unterpakete mit je einer Handvoll
> kleiner Module vor. Das ist beim Zusammenlegen des Repositorys
> aufgegeben worden – die Dateiliste war länger als hilfreich. Der
> heutige, flache Schnitt:

```
drawing_checker/
├── app.py                # Einstieg: GUI, --headless, --check-rules, SAP-Werkzeuge
├── kern.py               # Datenmodelle, Paketzugriff, Laufzustand, Haushalt
├── ablauf.py             # Orchestrator: Liste abarbeiten, blockweise, abbrechbar
├── zeichnung.py          # PDF laden, Metadaten, Maße, Form- und Lagetoleranzen
├── ocr.py                # Tesseract-Weg für gescannte PDFs + Selbstprüfung
├── regeln.py             # Regelmechanik, Profile, Validierung der Wissenspakete
├── pruef_zeichnung.py    # Vollständigkeit, Schriftfeld, Sprache, Maßstab, Verfahren
├── pruef_bemassung.py    # Maße, Toleranzen, GPS
├── pruef_werkstoff.py    # Werkstoff, Verfahren, Gewicht, Beschaffung
├── pruef_geometrie.py    # STEP-Abgleich, Silhouettenprojektion (OpenCascade)
├── bericht.py            # Markiertes Bild, Excel-Rückschrieb, HTML-Bericht
├── gui.py                # Hauptfenster (PySide6)
├── sap_ablauf.py         # .vbs-Mitschnitt einlesen und abspielen
├── sap_sitzung.py        # Sitzung, Fenstergrenze, Popups, Download, Wächter
├── sap_ymatdocs.py       # Adapter-Schnittstelle, echter Weg, Mock, Testsitzung
├── sap_cli.py            # Kommandozeilenwerkzeuge rund um SAP
└── rules/                # Das Fachwissen als YAML - vier Dateien, vom Anwender
    ├── profiles.yaml     #   pflegbar, deshalb bewusst NICHT zusammengelegt
    ├── materials.yaml
    ├── norms.yaml
    └── beschaffung.yaml

tests/     conftest.py + 5 Testdateien (Regeln, Geometrie, SAP, Ablauf, Auslieferung)
tools/     paket.py (ZIP + Einzeldatei), messen.py (OCR, Langlauf, Kalibrierung, Normen)
mockdata/  daten.py (Mockpakete, Kalibrierzeichnungen, Fehlerinjektion)
```

---

### 3. Technologie-Entscheidungen

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

### 4. Kernbausteine im Detail

#### 4.1 GUI (bedienerfreundlich, für Nicht-Techniker)

- Drei-Schritte-Wizard: **1) Datei wählen → 2) Spalte anklicken → 3) Start**.
- Spaltenwahl: Tabelle rendert die ersten ~50 Zeilen; Klick auf einen Spaltenkopf
  markiert die Spalte, Tool validiert sofort („412 Materialnummern erkannt,
  3 Zeilen leer/ungültig – werden übersprungen").
- Während des Laufs: Fortschrittsbalken, aktuelle Materialnummer, Ampel-Liste der
  bereits geprüften Nummern (grün = ok, gelb = Findings, rot = Prüfung fehlgeschlagen).
- Keine Stacktraces für den Anwender – Fehler in Klartext, Details ins Logfile.
- Buttons: Pause, Fortsetzen, Abbrechen, „Ergebnisordner öffnen".

#### 4.2 SAP-Adapter (`sap_*.py`)

- Verbindung über `GetObject("SAPGUI")` → `ScriptingEngine` → vorhandene oder neue
  Session auf **P11**.
- `ymatdocs.py` kapselt den kompletten Transaktionsablauf **bis zum ZIP-Download**.
  **Der morgen erstellte .vbs-Mitschnitt ist die Referenz** – er wird mechanisch
  nach Python portiert (gleiche Element-IDs), ergänzt um Waits/Existenzprüfungen
  statt fixer Sleeps. Zusätzlich abzudecken: der SAP-Datei-Dialog beim Download
  (Zielpfad je Materialnummer setzen, „Datei existiert"-Dialog, Warten bis das
  ZIP vollständig geschrieben ist – Größe stabil / kein Lock).
- `kern.py` entpackt das ZIP in einen Arbeitsordner je Materialnummer und
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

#### 4.3 Watchdog & automatischer P11-Neustart

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

#### 4.4 Check-Engine (`regeln.py` + `pruef_*.py`)

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

1. `zeichnung.py` extrahiert Maßzahlen aus dem PDF-Textlayer
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

#### 4.5 Reporting (`report/`)

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

### 5. Geklärte und offene Punkte

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

### 6. Meilensteine

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
