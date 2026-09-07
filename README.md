# Drawing Checker

Internes Tool zur automatisierten Prüfung technischer Zeichnungen je
Materialnummer: fachliche Prüfung der technischen Kommunikation nach
allgemeinen Normen (Sicht: internationaler Einkauf), Sprach-Check
(deutschsprachige Zeichnungen sind ein Finding) und Geometrieabgleich der
Zeichnung gegen das STEP-Modell (Erkennung falsch gespeicherter
Konfigurationen). Ergebnisse: annotiertes Zeichnungsbild je Materialnummer
plus Rückschrieb in eine Kopie der Input-Excel.

**Das ganze Projekt sind drei Dateien:**

| Datei | Was drin ist |
|---|---|
| `drawing_checker.py` | Das Programm – Prüfregeln, SAP-Anbindung, OCR, Geometrie, GUI, Berichte. Dazu eingebettet: die Wissenspakete (YAML), die Mockdaten-Erzeugung, die Werkzeuge (Paketbau, Messplätze) und am Dateiende die komplette Testsuite. |
| `Start.bat` | Einrichtung und Menü für Windows. Doppelklick genügt. |
| `README.md` | Diese Datei: Anwenderanleitung, Entwicklerdoku, Regelkatalog, SAP-Durchstich, Übergabe. |

Die Datei `drawing_checker.py` ist bewusst lang (rund 17 000 Zeilen). Sie
ist in Abschnitte gegliedert, jeder mit einem Kopf `# ====` und Namen –
im Editor nach `# ==== ` suchen oder die Gliederung unten benutzen. Warum
eine Datei: Weitergabe, Upload und Übersicht litten unter über hundert
Einzeldateien; eine Datei kann man nicht falsch zusammenstellen.

Inhalt dieser README:

1. [Für Anwender: Einstieg und Bedienung](#für-anwender-einstieg-und-bedienung)
2. [Für die Entwicklung](#für-die-entwicklung) – Installation, Aufrufe, Gliederung der Datei
3. [Fachliche Bausteine](#geometrieprüfung-im-detail) – Geometrie, Maßstab, OCR, Gewicht, Laufsteuerung
4. [SAP-Durchstich – Ablauf für den Einsatztag](#sap-durchstich--ablauf-für-den-einsatztag)
5. [Regelkatalog: alle Regeln im Klartext](#regelkatalog-alle-regeln-im-klartext)
6. [Kalibrierzeichnungen: Herkunft](#kalibrierzeichnungen-herkunft)
7. [Übergabe – Stand und nächste Schritte](#übergabe--stand-und-nächste-schritte)
8. [Hinweise für Claude-Sessions](#hinweise-für-claude-sessions)

---

# Für Anwender: Einstieg und Bedienung

```text
===========================================================
 DRAWING CHECKER - Bitte zuerst lesen (2 Minuten)
===========================================================

SO GEHT ES LOS
--------------
1. Es gibt zwei Wege hierher - beide fuehren zum selben Ordner:

   a) DrawingChecker_Setup.bat doppelklicken. Sie entpackt sich
      selbst in den Ordner DrawingChecker daneben und macht bei
      Schritt 2 von allein weiter. Fertig - Schritt 2 entfaellt.
      (Meldet der Virenscanner etwas, Weg b) nehmen.)

   b) DrawingChecker.zip entpacken: Rechtsklick -> "Alle
      extrahieren ...", Ziel zum Beispiel: C:\Tools\DrawingChecker
      WICHTIG: Nicht aus dem ZIP heraus starten - sonst gehen alle
      Ergebnisse beim Schliessen verloren.

2. Doppelklick auf   Start.bat

   Beim ersten Mal richtet sich das Programm selbst ein. Das dauert
   je nach Netz 5 bis 15 Minuten. Bitte das schwarze Fenster offen
   lassen, auch wenn zwischendurch nichts passiert.

3. Danach erscheint ein Menue. Alles Weitere laeuft ueber Zahlen -
   es muss nichts eingetippt werden ausser der jeweiligen Nummer.


DER ERSTE TAG - REIHENFOLGE
---------------------------
Zuerst muss dem Programm einmalig beigebracht werden, wie die
SAP-Transaktion YMATDOCS bedient wird. Das geschieht nicht durch
Programmieren, sondern durch eine Aufzeichnung aus SAP:

 A) In SAP:  Statusleiste unten rechts -> "Skript aufzeichnen und
    abspielen" -> Aufzeichnen. Dann die Transaktion EINMAL komplett
    durchspielen: /nYMATDOCS, Materialnummer eintragen, ausfuehren,
    ZIP herunterladen, Ordner und Dateiname im Dialog eintragen,
    speichern, mit F3 zurueck auf das Selektionsbild.
    Aufzeichnung stoppen. Die .vbs liegt meist unter
    Dokumente\SAP\SAP GUI\.

    Tipp: Vorher unter SAP Logon -> Optionen -> Barrierefreiheit &
    Skripting den Haken bei "Hinweis bei Skriptanbindung" ENTFERNEN,
    sonst kommt bei jeder Materialnummer eine Rueckfrage.

 A2) Mehr wird nicht gebraucht: Aus der .vbs liest das Programm den
     Transaktionscode, die Eingabefelder, den Download-Knopf, den
     Datei-Dialog UND das SAP-System heraus. Nichts davon muss von
     Hand eingetragen werden.

 B) Im Menue von Start.bat:
      Punkt 2  -> die .vbs-Datei einlesen
                  (Datei einfach ins Fenster ziehen und Enter)
      Punkt 3  -> Trockenlauf ohne SAP: prueft, ob der Ablauf sitzt
      Punkt 4  -> eine echte Materialnummer testweise holen
      Punkt 1  -> der eigentliche Lauf ueber die Excel-Liste

    Der Mitschnitt laesst sich auch direkt im Programmfenster einlesen
    (Knopf "SAP-Mitschnitt (.vbs) einlesen ..."). Ohne Mitschnitt
    verweigert das Programm den Start und sagt, was fehlt.

 C) Wenn Punkt 4 scheitert: Punkt 5 zeigt den Aufbau des aktuellen
    SAP-Bildes. Damit laesst sich in der Datei
    regeln\ymatdocs_flow.yaml die passende Element-Nummer eintragen.
    Ausfuehrlich erklaert in README.md, Abschnitt SAP-Durchstich.


WENN ETWAS KLEMMT
-----------------
Das schwarze Fenster bleibt bei Fehlern offen und nennt die Ursache
im Klartext. Die drei haeufigsten:

 * "Kein Python ab Version 3.10 gefunden"
   -> Python fehlt. Ueber das Firmen-Softwarecenter anfordern oder
      von python.org installieren ("Add python.exe to PATH" ankreuzen).

 * "Die Installation ist fehlgeschlagen"
   -> Meist kein Zugang zum Paketserver (Proxy). Die Datei
      logs\einrichtung.log enthaelt die genaue Meldung.
      Fuer die IT: benoetigt wird Zugriff auf pypi.org bzw. den
      Firmen-Spiegel. Mit gesetztem Proxy geht es so:
         set HTTPS_PROXY=http://proxy.firma.de:8080
         Start.bat
      Gibt es gar keinen Netzzugang, koennen die Pakete auf einem
      anderen Rechner vorbereitet werden:
         pip download -d wheels pymupdf openpyxl pillow pandas PyYAML ^
             PySide6-Essentials cadquery-ocp pytesseract pywin32
      Den Ordner "wheels" mitliefern und einmalig aufrufen:
         .venv\Scripts\python -m pip install --no-index ^
             --find-links wheels pymupdf openpyxl pillow pandas PyYAML ^
             PySide6-Essentials cadquery-ocp pytesseract pywin32

 * "Das Programm laeuft aus dem ZIP-Archiv heraus"
   -> Erst entpacken (Schritt 1 oben).

Zum Nachlesen:
  README.md           diese Datei. Weiter unten: SAP-Durchstich, alle
                      98 Pruefregeln im Klartext, eigene Werkstoffe und
                      Normen pflegen, Uebergabe an die Entwicklung

===========================================================


===========================================================
 AUSFUEHRLICHE ANLEITUNG
===========================================================

DRAWING CHECKER - KURZANLEITUNG
===============================

Fuer Anwenderinnen und Anwender. Zwei Seiten, mehr braucht es nicht.


Was das Programm tut
--------------------

Es holt zu jeder Materialnummer Ihrer Liste das Zeichnungspaket aus SAP
(Transaktion YMATDOCS), prueft die Zeichnung auf Vollstaendigkeit,
Normverstoesse und fachliche Widersprueche, vergleicht sie mit dem
3D-Modell - und schreibt das Ergebnis in Ihre Excel-Tabelle zurueck.

Es entscheidet nicht, ob eine Zeichnung freigegeben wird. Es sagt
Ihnen, wo Sie hinsehen muessen.


Einmalig: SAP-Mitschnitt einlesen
---------------------------------

Das Programm lernt die Transaktion aus einer einzigen Datei - dem
.vbs-Mitschnitt, den SAP beim Aufzeichnen erzeugt. Mehr braucht es
nicht: Transaktionscode, Eingabefelder, der Download-Knopf, der
Datei-Dialog und sogar das SAP-System werden daraus gelesen.

1. In SAP unten rechts: *Skript aufzeichnen und abspielen* -> Aufzeichnen.
2. Die Transaktion einmal komplett durchspielen (Materialnummer eintragen,
   ausfuehren, ZIP herunterladen, speichern, mit F3 zurueck).
3. Aufzeichnung stoppen - die Datei liegt meist unter
   Dokumente\SAP\SAP GUI\.
4. Im Programm auf "SAP-Mitschnitt (.vbs) einlesen ..." klicken.

Danach steht oben gruen, was verstanden wurde: Transaktion, System,
Materialnummer-Feld und Download-Schritt. Das war es - ab jetzt laeuft
alles automatisch.


In fuenf Schritten
-----------------

1. Excel vorbereiten. Eine Spalte mit den Materialnummern, eine
   Ueberschriftenzeile. Sonst nichts. Die Datei darf ruhig weitere Spalten
   enthalten.
2. Programm starten: Doppelklick auf Start.bat im
   Programmordner (oder auf die Verknuepfung "Drawing Checker" auf dem
   Desktop). Beim allerersten Start richtet sich das Programm selbst ein -
   das dauert einige Minuten, das Fenster dabei offen lassen. SAP muss
   offen und angemeldet sein; das Programm nutzt Ihre bestehende Anmeldung.
3. Datei waehlen und auf die Spalte zeigen, in der die Materialnummern
   stehen. Das Programm zeigt eine Vorschau der erkannten Nummern.
4. Starten. Der Lauf arbeitet die Liste selbststaendig ab. Sie koennen
   ihn pausieren und fortsetzen; nach einem Abbruch (auch nach einem
   SAP-Absturz oder einem Neustart des Rechners) macht er dort weiter, wo
   er stehengeblieben ist.
5. Ergebnis ansehen. Am Ende oeffnet sich der Bericht. Die
   Ergebnis-Excel liegt neben Ihrer Ausgangsdatei mit dem Zusatz
   _geprueft.


Waehrend des Laufs
-----------------

- Die Ergebnis-Excel waechst mit. Nach jeder Materialnummer steht die
  Zeile auf der Platte. Auch wenn der Rechner ausgeht, ist alles bis dahin
  gesichert.
- Blockweise: Nach je 25 Materialnummern (einstellbar) sichert das
  Programm einen Zwischenstand, schreibt den Bericht neu und raeumt SAP auf.
  Der Fortschrittsbalken zeigt "Block 3 von 12".
- Pause haelt den Lauf an, ohne etwas zu verlieren; Abbrechen beendet
  ihn sauber - auch mitten in einem Download.
- Beim naechsten Start fragt das Programm von selbst: "Zu dieser Liste
  gibt es einen unfertigen Lauf, 240 Nummern sind geprueft - dort
  fortsetzen?" Ein Klick auf Ja, und es geht genau dort weiter.
- SAP: Das Programm nutzt Ihre bestehende Anmeldung und oeffnet
  hoechstens ein eigenes Fenster - nie mehr als fuenf insgesamt. Sind schon
  fuenf offen, meldet es das, statt Ihnen das letzte Fenster wegzunehmen.


Was Sie zurueckbekommen
----------------------

Je Materialnummer eine Zeile mit:

| Spalte | Inhalt |
|---|---|
| Status | OK / Findings / Fehlgeschlagen / Uebersprungen |
| Schwerste Bewertung | K.O., Fehler, Pruefen oder Hinweis |
| Festgestellte Maengel | im Klartext, mit Regelcode |
| Letzte Aenderung | das spaeteste Datum, das auf der Zeichnung steht |
| Fertigungsverfahren | was das Programm erkannt hat (Fraesen, Schweissen ...) |
| Bild | Verweis auf die annotierte Zeichnung |
| Geprueft am | Datum und Uhrzeit der Pruefung |

Dazu im Ergebnisordner: das annotierte Zeichnungsbild je Materialnummer
(nummerierte Fundstellen mit Legende), ein HTML-Bericht mit den haeufigsten
Maengeln und eine findings.csv fuer eigene Auswertungen.


Die vier Bewertungen
--------------------

- K.O. - Paket unbrauchbar oder das 3D-Modell passt nicht zur
  Zeichnung. Nicht anfragen, erst klaeren.
- Fehler - klare Beanstandung, die Zeichnung gehoert nachgebessert.
- Pruefen - das Programm ist sich nicht sicher. Kurz ansehen, oft ist
  es in Ordnung.
- Hinweis - nur zur Information.


Wenn etwas nicht stimmt
-----------------------

- Eine Meldung wirkt falsch. Das annotierte Bild zeigt, worauf sie sich
  bezieht. Melden Sie den Regelcode (z. B. GT.GENERAL_TOL) an die
  Systembetreuung - Regeln lassen sich einzeln abschalten oder anders
  bewerten, ohne das Programm zu aendern.
- "Pruefung basiert auf OCR". Die Zeichnung war ein Scan ohne
  Textebene. Die Erkennung ist dann unsicher, deshalb wird nichts hart als
  Fehler gemeldet. Bei Beanstandungen bitte die Zeichnung selbst ansehen.
- Der Lauf haelt an. Meist ist die Platte voll oder SAP haengt. Die
  Meldung sagt, was zu tun ist; nach dem Beheben mit "Fortsetzen"
  weiterlaufen lassen - bereits gepruefte Zeilen bleiben erhalten.
- Die Ergebnisdatei laesst sich nicht schreiben. Sie ist in Excel
  geoeffnet. Das Programm weicht auf eine Datei mit dem Zusatz _neu aus;
  besser: Excel schliessen, solange der Lauf laeuft.


Wenn der Start nicht klappt
---------------------------

Das schwarze Fenster bleibt bei Problemen offen und nennt die Ursache im
Klartext - meist eines von dreien:

- "Kein Python ab Version 3.10 gefunden": Python fehlt auf dem Rechner.
  Die Meldung nennt den Downloadlink; im Firmenumfeld ueber das
  Softwarecenter anfordern.
- "Die Installation ist fehlgeschlagen": meist kein Zugang zum
  Paketserver (Proxy). Bitte die Datei logs\einrichtung.log an die
  Systembetreuung geben.
- "Die vorhandene Umgebung ist unbrauchbar": passiert, wenn der Ordner
  verschoben oder kopiert wurde. Das Programm baut sie selbst neu auf;
  erzwingen laesst sich das mit Start.bat neu.


Was das Programm nicht kann
---------------------------

- Es liest keine Konstruktionsabsicht. Ob eine enge Toleranz noetig ist,
  entscheiden Sie.
- Bei Scans ohne Textebene sieht es nur, was die Texterkennung hergibt.
- Es prueft die Zeichnung, nicht das Bauteil. Ein sauber gezeichneter
  Unsinn bleibt unentdeckt.
```

---

# Für die Entwicklung

## Installation (Entwicklungsrechner)

Es gibt kein Paket zu installieren – nur Abhängigkeiten:

```bash
pip install "pymupdf>=1.24" "openpyxl>=3.1" "pillow>=10" "pandas>=2" "PyYAML>=6" "PySide6-Essentials>=6.6"
pip install "cadquery-ocp>=7.7"     # exakte STEP-Analyse (empfohlen; sonst nur Bounding-Box)
pip install "pytesseract>=0.3"      # OCR für gescannte Zeichnungen (+ Tesseract-Programm)
pip install "pywin32>=306"          # nur Windows: SAP GUI Scripting
pip install "pytest>=8"             # Tests
```

Genau diese Liste steht auch in `Start.bat` (Abschnitt 4) – sie ist dort
die einzige Quelle für den Anwenderrechner. Ändert sich die Liste, dort
`PAKETSTAND` hochzählen, dann installiert `Start.bat` beim nächsten Start
nach.

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

## Alle Aufrufe

```bash
python drawing_checker.py                          # GUI (echtes SAP P11, nur Windows)
python drawing_checker.py --mock mockdata/out      # GUI im Testmodus (ZIPs aus Ordner)
python drawing_checker.py --headless --mock mockdata/out \
    --excel mockdata/out/Materialliste_Mock.xlsx --column C
python drawing_checker.py --check-rules            # Wissenspakete validieren
python drawing_checker.py --list-rules             # Regelkatalog je Profil
python drawing_checker.py --export-rules [ordner]  # YAMLs zum Bearbeiten nach regeln/
python drawing_checker.py --ocr-check [x.pdf]      # OCR prüfen/vorführen
python drawing_checker.py --sap-import-vbs x.vbs   # Mitschnitt -> Ablauf
python drawing_checker.py --sap-dry-run 10473215   # Ablauf ohne SAP prüfen
python drawing_checker.py --sap-test 10473215      # eine Materialnummer echt holen
python drawing_checker.py --sap-dump               # Elementbaum des SAP-Bildes

python drawing_checker.py mockdata bauen           # Mockpakete nach mockdata/out
python drawing_checker.py mockdata quellen         # Kalibrierzeichnungen auspacken
python drawing_checker.py mockdata fehler <q> <z>  # Referenz- und Fehlerpakete

python drawing_checker.py messen ocr               # OCR-Güte messen
python drawing_checker.py messen langlauf --count 200
python drawing_checker.py messen kalibrier <ordner>
python drawing_checker.py messen normen <csv> <yaml>

python drawing_checker.py paket [--nur zip|bat]    # Auslieferung nach dist/

python -m pytest drawing_checker.py -q             # Tests (~6 min, liegen am Dateiende)
QT_QPA_PLATFORM=offscreen python drawing_checker.py --mock mockdata/out  # GUI headless
```

## Gliederung von drawing_checker.py

Die Abschnitte in der Reihenfolge, wie sie in der Datei stehen. Jeder
beginnt mit `# ==== <name>`:

| Abschnitt | Inhalt |
|---|---|
| `wissenspakete` | Die vier YAML-Wissenspakete als Text (profiles, materials, norms, beschaffung) |
| `kern` | Datenmodelle, Paketzugriff, Laufzustand (Resume), Haushalt (Speicher, Platte) |
| `zeichnung` | PDF laden, Metadaten, Maßextraktion, Form- und Lagetoleranzen |
| `regeln` | Regelmechanik, Profile, Validierung der YAMLs, `--export-rules` |
| `pruef_werkstoff` | Werkstoff, Verfahren, Gewicht, Beschaffung |
| `pruef_zeichnung` | Vollständigkeit, Schriftfeld, Sprache, Maßstab, Verfahrenserkennung |
| `pruef_bemassung` | Maße, Toleranzen, GPS |
| `pruef_geometrie` | STEP-Abgleich, Silhouettenprojektion (alles OpenCascade, träge geladen) |
| `ocr` | Texterkennung für Scans und ihre Selbstprüfung |
| `bericht` | Markiertes Bild, Excel-Rückschrieb, HTML-Bericht |
| `sap_sitzung` | Adapter-Schnittstelle, Sitzung, Fenstergrenze, Popups, Download, Wächter, Diagnose |
| `sap_ablauf` | .vbs-Mitschnitt einlesen und abspielen |
| `sap_ymatdocs` | Echter YMATDOCS-Weg, Mock aus Ordner, Testsitzung |
| `sap_cli` | Kommandozeilenwerkzeuge rund um SAP |
| `ablauf` | Orchestrator: Liste abarbeiten, blockweise, abbrechbar, fortsetzbar |
| `gui` | Hauptfenster (PySide6; ohne PySide6 läuft alles andere weiter) |
| `app` | Einstieg, Argumente, Unterbefehle |
| `mockdata` | Mockpakete, Kalibrierzeichnungen, Fehlerinjektion |
| `paket` | Auslieferung: ZIP und selbstentpackende .bat |
| `messen` | Messplätze: OCR-Güte, Langlauf, Kalibrierauswertung, Normimport |
| `tests` | Die Testsuite – nur aktiv, wenn pytest die Datei lädt |

Die Wissenspakete sind eingebettet, damit das Programm eine Datei bleibt.
Bearbeiten: `python drawing_checker.py --export-rules` schreibt die vier
YAMLs nach `regeln/`; was dort liegt, überlagert die eingebauten Regeln
(auch über `DRAWING_CHECKER_RULES`). Änderungen, die ins Programm sollen,
kommen in den Abschnitt `wissenspakete`.

## Nutzung

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
python drawing_checker.py mockdata bauen            # erzeugt mockdata/out/
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
python -m pytest drawing_checker.py -q        # inkl. End-to-End über die Mockdaten
```

Die Tests stehen am Ende von `drawing_checker.py` unter `if "pytest" in
sys.modules:` – beim normalen Start existieren sie nicht, pytest sieht sie.
Mockdaten werden je Lauf erzeugt; die Tests an den echten
Kalibrierzeichnungen überspringen sich, wenn `echt_quellen.zip` fehlt
(siehe [Kalibrierzeichnungen](#kalibrierzeichnungen-herkunft)).

## Geometrieprüfung im Detail

Der Abgleich Zeichnung ↔ STEP läuft über vier unabhängige Indizien, damit
eine falsch gespeicherte Konfiguration auch dann auffällt, wenn ein
Einzelkriterium unscharf ist:

1. **Hüllmaße** – größte Zeichnungsmaße vs. optimale Bounding-Box des
   Modells, plus Raumdiagonalen-Prüfung (K.O.-Kriterium).
2. **Masse** – Gewichtsangabe im Schriftfeld vs. STEP-Volumen × Dichte des
   erkannten Werkstoffs (Dichten stehen in `materials.yaml` (eingebettet; `--export-rules`)).
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
Das Tool erkennt die Rahmen deshalb geometrisch (Abschnitt `zeichnung`) und wertet
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
python drawing_checker.py --ocr-check                 # Installation prüfen
python drawing_checker.py --ocr-check zeichnung.pdf   # Leseprobe
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

Die Güte ist messbar: `python drawing_checker.py messen ocr` (nimmt ohne Angabe die
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

Der Zielrechner braucht `drawing_checker.py`, `Start.bat` und diese README
im selben Ordner – drei Dateien, mehr nicht. Wer es auf **eine** Datei
bringen will:

```bash
python drawing_checker.py paket             # dist/DrawingChecker_Setup.bat + dist/DrawingChecker.zip
python drawing_checker.py paket --nur bat   # nur die selbstentpackende .bat
```

* **`dist/DrawingChecker_Setup.bat`** trägt die drei Dateien als Base64 in
  sich. Doppelklick: entpackt sich in den Ordner `DrawingChecker` neben
  sich und startet die Einrichtung. Nichts wird in Windows installiert,
  nichts in der Registry geändert. Manche Virenscanner sehen
  selbstentpackende Batch-Dateien kritisch – dann die ZIP-Fassung nehmen.
* **`dist/DrawingChecker.zip`** ist der unauffällige Weg: entpacken – es
  entsteht der Ordner `DrawingChecker` – und darin `Start.bat` doppelklicken.

Beide prüfen sich beim Bauen selbst (entpacken, `--check-rules` im
entpackten Stand). `dist/` ist nicht im Repository – vor der Weitergabe
bauen, dann wird nie ein alter Stand verteilt.



## Kalibrierung an echten Zeichnungen

`echt_quellen.zip` (nicht im Repository) enthält **84 echte, frei lizenzierte
Fertigungszeichnungen** (28 mit STEP) aus OreSat (CERN-OHL-S v2) und
ShapeOko (CC BY-SA 3.0) – Frästeile, Blech, Guss, Baugruppen, in mm und in
Zoll, ISO- und ASME-Bemaßung. Sie liegen als **ein** Archiv im Repository
(als über hundert Einzeldateien haben sie jede Dateiliste zugemüllt);
`python drawing_checker.py mockdata quellen` packt sie nach `.echt_quellen/` aus,
die Werkzeuge tun das bei Bedarf von selbst. `python drawing_checker.py mockdata fehler`
erzeugt daraus je
Zeichnung ein unverändertes Referenzpaket und eines mit gezielt
eingebautem Fehler; `python drawing_checker.py messen kalibrier` stellt beides
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

`python drawing_checker.py messen langlauf` prüft, ob das Werkzeug stundenlang durchhält: es baut
beliebig viele Materialnummern aus Mockpaketen, lässt den normalen
Orchestrator darüberlaufen und misst Speicher, Plattenbedarf und Zeit je
Nummer.

```bash
python drawing_checker.py messen langlauf --count 200
```

Damit wurden zwei echte Speicherlecks gefunden (der STEP-Leser von
OpenCascade und der interne Zwischenspeicher von PyMuPDF) – vorher wuchs
der Prozess um rund 12 MB je Materialnummer, jetzt um 0,04 MB. Während des
Laufs werden entpackte Pakete nach der Prüfung gelöscht und der freie
Plattenplatz überwacht; wird es eng, hält der Lauf geordnet an und ist
fortsetzbar.

## Regelkatalog anpassen

`profiles.yaml` (Abschnitt `wissenspakete`, `--export-rules`) – Regeln je Materialgruppe
(default/guss/schweiss) an-/abschalten, Severities und Toleranzbänder für
den Geometrieabgleich ändern. Profile erben per `inherit` voneinander.

## SAP-Anbindung (Durchstich am Einsatztag)

Der Transaktionsablauf wird **nicht programmiert, sondern aufgezeichnet**:
der .vbs-Mitschnitt aus SAP wird eingelesen, in einen abspielbaren Ablauf
übersetzt und mit Platzhaltern (`{material}`, `{target_dir}`, `{filename}`)
versehen. Vier Schritte:

```bat
python drawing_checker.py --sap-import-vbs ymatdocs.vbs   # 1. einlesen
python drawing_checker.py --sap-dry-run 10473215          # 2. ohne SAP prüfen
python drawing_checker.py --sap-test   10473215           # 3. echt, ein Material
python drawing_checker.py                                 # 4. Dauerlauf (GUI)
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
4. Auslieferung: `python drawing_checker.py paket` (siehe Weitergabe).

Weiteres Wissen einpflegen (Normen, Werkstoffe, Regeln) ohne Code: siehe
[Regelkatalog](#regelkatalog-alle-regeln-im-klartext). Echte Kalibrier-Zeichnungen: siehe
Abschnitt „Kalibrierzeichnungen: Herkunft“
(die Zeichnungen selbst: `echt_quellen.zip` (nicht im Repository)).


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
> (`_looks_like_not_found` in Abschnitt `sap_ymatdocs`).

---

### 1. Mitschnitt einlesen

```bat
python drawing_checker.py --sap-import-vbs "C:\...\ymatdocs.vbs"
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
python drawing_checker.py --sap-dry-run 10473215
```

Spielt den Ablauf gegen eine simulierte Session ab und beantwortet:
Werden alle Platzhalter aufgelöst? Landet die Materialnummer in einem
Feld? Öffnet der Auslöser den Datei-Dialog, und entsteht danach die Datei
am erwarteten Ort? Rückgabewert 0 = in Ordnung.

### 3. Einzeltest gegen echtes SAP

```bat
python drawing_checker.py --sap-test 10473215
```

Verbindet sich mit P11 (bestehende Anmeldung wird genutzt), führt den
Ablauf einmal aus und legt das Paket unter `sap_test\` ab. Danach wird der
ZIP-Inhalt aufgelistet: wie viele PDF, wie viele STEP.

Schlägt es fehl, wird automatisch eine Diagnose geschrieben
(`sap_test\diagnose_<matnr>.txt`): Elementbaum des aktuellen Bildes,
Statuszeile, Fenstertitel. Daraus lassen sich die richtigen Element-IDs
ablesen. Zusätzlich jederzeit:

```bat
python drawing_checker.py --sap-dump
```

### 4. Dauerlauf

```bat
python drawing_checker.py            # GUI, Standardweg für Anwender
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
  `default_watch_dirs` (Abschnitt `sap_sitzung`) ergänzen oder im Datei-Dialog den
  Zielordner erzwingen (`{target_dir}`).
- **Scripting-Hinweisdialog erscheint bei jedem Aufruf** → SAP-GUI-Option
  aus Schritt 0.2 abschalten.
- **„pywin32 fehlt"** → `pip install pywin32` (nur Windows).

### Aufbau der SAP-Schicht (zum Nachlesen)

| Datei | Aufgabe |
|---|---|
| Abschnitt `sap_ablauf` (Parser) | .vbs → Ablauf, erkennt Transaktion, Materialfeld, Dialogfelder, Download-Auslöser |
| Abschnitt `sap_ablauf` (Player) | Ablaufmodell + Player; `call`/`set_prop` bilden **jede** Scripting-Anweisung ab (auch ALV-Grid) |
| Abschnitt `sap_ymatdocs` | Ablauf je Materialnummer, Statusauswertung, Notnagel-Ablauf |
| Abschnitt `sap_sitzung` (Sitzung) | COM-Anbindung an P11, Wiederverwendung bestehender Sitzungen |
| Abschnitt `sap_sitzung` (Wächter) | Neustart von SAP Logon nach Absturz |
| Abschnitt `sap_sitzung` (Popups) | Dialogbehandlung |
| Abschnitt `sap_sitzung` (Download) | Erkennung der fertigen ZIP-Datei |
| Abschnitt `sap_sitzung` (Diagnose) | Elementbaum, Screenshot, Fehlerbericht |
| Abschnitt `sap_ymatdocs` (Testsitzung) | simulierte Session für Trockenlauf und Tests |


---

# Regelkatalog: alle Regeln im Klartext

Alle 98 Prüfregeln des Drawing Checkers – Grundlage für die Abstimmung mit
dem Fachbereich. Jede Regel ist über `profiles.yaml` (Abschnitt `wissenspakete`)
(bzw. ein eigenes Paket in `regeln/`) einzeln abschaltbar, und ihre Severity
ist frei einstellbar. Die aktuell aktiven Regeln zeigt
`python drawing_checker.py --list-rules`.

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
`beschaffung.yaml` (eingebettet; `--export-rules`) und sind ohne Codeänderung erweiterbar.

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
Abschnitt `wissenspakete` von `drawing_checker.py` – oder, nach
`--export-rules`, als Dateien in `regeln/`. Wer Fachwissen hat, erweitert
YAML – keinen Code.
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
3. **Prüfen:** `python drawing_checker.py --check-rules` validiert alle Pakete und
   meldet Probleme in Klartext mit Datei und Eintrag (leeres/falsches Feld,
   Regex-Tippfehler, unbekannte Kategorie/Severity, doppelte Namen). Die GUI
   macht dieselbe Prüfung beim Start und zeigt Funde als Warnung.
4. **Sicherheitsnetz:** Ein fehlerhafter Eintrag bricht nie den Prüflauf ab –
   er wird ignoriert und geloggt, der Rest des Pakets lädt normal.

### Die drei Wissensspeicher

| Datei | Inhalt | Wer pflegt |
|---|---|---|
| `profiles.yaml` (eingebettet; `--export-rules`) | Regeln je Materialgruppe: an/aus, Severity, Schlüsselwörter, Toleranzbänder für den Geometrieabgleich | Fachbereich |
| `materials.yaml` (eingebettet; `--export-rules`) | Werkstoffe: Erkennungsmuster + Eigenschaften (schweißgeeignet, härtbar, verzinkbar, eloxierbar, Guss) → speist die Widerspruchsprüfung | Fachbereich/Schweißaufsicht |
| `norms.yaml` (eingebettet; `--export-rules`) | Zurückgezogene/ersetzte Normen mit Hinweis auf den Nachfolger | Normenstelle |
| `beschaffung.yaml` (eingebettet; `--export-rules`) | Unbestimmte Formulierungen, nicht beziehbare Haus-/Konzernnormen, Vorzugsmaße für Halbzeuge | Einkauf/Arbeitsvorbereitung |

### Massenimport statt Handarbeit

1. **Normenverwaltung anzapfen (größter Hebel):** Nautos/Perinorm können
   Trefferlisten mit Status und Nachfolgedokument als CSV exportieren.
   `python drawing_checker.py messen normen export.csv regeln/norms_firma.yaml`
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

- `echt_quellen.zip` (nicht im Repository) enthält 84 echte Zeichnungen (auspacken mit
  `python drawing_checker.py mockdata quellen`); `python drawing_checker.py mockdata fehler`
  erzeugt daraus Pakete mit dokumentierten Soll-Fehlern (`MANIFEST.txt`).
- Nach jeder Wissensänderung: `python -m pytest drawing_checker.py -q` und einen
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

# Kalibrierzeichnungen: Herkunft

Die 84 echten Zeichnungen (25 MB) liegen **nicht** im Repository. Sie
stehen in der Git-Historie und lassen sich in einer Zeile zurückholen –
die Datei gehört neben `drawing_checker.py` und ist per `.gitignore`
ausgeschlossen:

```bash
git show c80d62e:mockdata/echt_quellen.zip > echt_quellen.zip
python drawing_checker.py mockdata quellen        # packt nach .echt_quellen/ aus
```

Ohne das Archiv überspringen sich die betroffenen Tests (Markierung
`needs_echt`); alles andere läuft.


Reale, frei lizenzierte Fertigungszeichnungen (mit passenden STEP-Modellen,
wo verfügbar) zur Kalibrierung des Checkers. Nur für interne Test- und
Entwicklungszwecke; Lizenzhinweise beachten.

**Stand: 84 Zeichnungen, davon 28 mit STEP-Modell.**


Der Satz ist bewusst breit: Frästeile, Blechteile, Wellen/Shims, Guss- und
Baugruppenzeichnungen, in Millimeter und in Zoll, ISO- und ASME-Bemaßung,
sauber und schlampig bemaßt. Genau daran zeigt sich, ob eine Regel trägt
oder nur auf der eigenen Mustervorlage funktioniert.

## OreSat / PSAS (Portland State Aerospace Society) — 56 Zeichnungen

Quelle: https://github.com/oresat/oresat-structure — Lizenz: **CERN-OHL-S v2**.
Professionelle SolidWorks-Fertigungszeichnungen (ASME Y14.5, überwiegend in
Millimeter) mit STEP-Modellen. Enthalten sind unter anderem:

- Rahmen der Satellitenstruktur (1U/1.5U/2U/3U, jeweils ±X und Y)
- Kartenkeile in mehreren Varianten (CardWedge*)
- Kamera- und Optikteile (CassegrainBase, lensmount, Shims, Baffle)
- Thermik (copperThermalMass, thermalStrap, thermalClamp)
- Reaktionsräder (MountingBeam, MotorBracket, RWWeight, MagnetHolder)
- Vibrationsprüfvorrichtungen, Montagejigs, Endkarten

Dateien tragen das Präfix `oresat_`; die sieben zuerst aufgenommenen
Zeichnungen behielten ihre ursprünglichen Namen (CassegrainBase.pdf,
lensmount.pdf, copperThermalMass.pdf, thermalStrap.pdf, supportBracket.pdf,
OreSat_InhibitPin.pdf, OreSat_PushPlate.pdf).

## ShapeOko / buildlog.net — 28 Zeichnungen

Quelle: https://github.com/shapeoko/ShapeOko — Lizenz: **CC BY-SA 3.0**.
Inventor-/SolidWorks-Zeichnungen einer offenen CNC-Fräse: Blechteile,
Aluminiumprofile, Platten, Baugruppen. Teilweise in Zoll bemaßt und mit
unvollständigen Schriftfeldern – wertvoll, weil genau solche Zeichnungen im
Einkauf auftauchen.

Dateien tragen das Präfix `shapeoko_`; drei Zeichnungen der ersten Runde
heißen weiterhin DW660_Mount.pdf, MSK01-03.pdf und SM-S02.pdf.

## Bewusst NICHT aufgenommen

- **Katalogblätter von Händlern** (McMaster-Carr u. Ä.): keine
  Fertigungszeichnungen, sondern Referenzblätter zugekaufter Normteile.
  Sie verfälschen die Fehlalarm-Statistik.
- **Zeichnungen unter NC-Lizenz** (z. B. Ultimaker-Teilezeichnungen,
  CC BY-NC): technisch hervorragend, aber die Lizenz erlaubt keine
  kommerzielle Nutzung – für ein Firmenwerkzeug ungeeignet.
- **Leiterplatten-Fertigungsunterlagen**: anderer Zeichnungstyp, andere
  Regeln.

## Nutzung

```bash
python drawing_checker.py mockdata fehler .echt_quellen <zielordner>
python drawing_checker.py --headless --mock <zielordner> \
    --excel <zielordner>/Materialliste_Echt.xlsx --column C
python drawing_checker.py messen kalibrier <zielordner>
```

Der erste Aufruf erzeugt je Zeichnung ein unverändertes **Referenzpaket**
und ein Paket mit **injizierten Fehlern** (MANIFEST.txt dokumentiert, was
wo eingebaut wurde). Die Auswertung stellt beides gegenüber: Was auf den
unveränderten Zeichnungen als „Fehler" gemeldet wird, ist Fehlalarm-Verdacht;
was nur auf den Fehlerpaketen anschlägt, ist echte Trefferleistung.

---

# Übergabe – Stand und nächste Schritte

Diese Datei ist für die **nächste Sitzung an einem anderen Rechner**
gedacht (Claude oder Mensch). Sie beantwortet: Was ist gebaut, was ist zu
tun, was muss man wissen, um nicht in dieselben Gruben zu fallen.

Stand: 06.09.2026, Branch `claude/drawing-validation-tool-inzji1`.

### 1. Was das Werkzeug heute kann

Vollständig gebaut und getestet (ohne SAP lauffähig über `--mock`):

- **98 Prüfregeln** in neun Gruppen (siehe Abschnitt „Regelkatalog“), Wissen in
  YAML im Abschnitt `wissenspakete` – Werkstoffe, Normen, Beschaffung.
- **Geometrieabgleich** gegen STEP über fünf unabhängige Indizien:
  Hüllmaße, Masse (Volumen × Dichte), Bohrbild, Konturprojektion (HLR)
  und Spiegelung (falsche Hand).
- **Masse-Plausibilität auch ohne STEP** (Hüllquader × Dichte).
- **OCR für gescannte Zeichnungen**, auf Zeichnungen getrimmt und messbar
  (`python drawing_checker.py messen ocr`).
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
python drawing_checker.py --sap-import-vbs ymatdocs.vbs
python drawing_checker.py --sap-dry-run 10473215
python drawing_checker.py --sap-test   10473215
python drawing_checker.py                      # GUI-Dauerlauf
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
python drawing_checker.py paket --nur bat     # dist/DrawingChecker_Setup.bat - Doppelklick,
                                # entpackt sich selbst und startet Start.bat
python drawing_checker.py paket --nur zip     # dist/DrawingChecker.zip - entpacken, Start.bat
```

Beide prüfen sich beim Bauen selbst (entpacken, `--check-rules` im entpackten
Stand). Die .bat ist der bequemere Weg, die ZIP der virenscannerfreundliche.
Nach jeder Code-Änderung **beide** neu bauen, sonst verteilt man den alten
Stand.

**Windows-Anwenderrechner:** Doppelklick auf `Start.bat` – richtet alles
ein und startet. `Start.bat neu` baut die Umgebung neu auf, `Start.bat
pruefen` lässt die Testsuite laufen. Das Skript ist bewusst ohne Umlaute
geschrieben (Codepage) und wird von der Testabschnitt in `drawing_checker.py` gegen die
klassischen Batch-Fallen geprüft (Blockklammern, Sprungziele, verzögerte
Expansion) – dort weitermachen, wenn es erweitert wird.

**Entwicklungsrechner:**

```bash
pip install pymupdf openpyxl pillow pandas PyYAML PySide6-Essentials cadquery-ocp pytesseract pytest
python -m pytest drawing_checker.py -q           # muss vollständig grün sein
python drawing_checker.py --check-rules
python drawing_checker.py --ocr-check
```

Zusätzlich nötig:

- **Tesseract** (nur für gescannte Zeichnungen): Windows über die
  UB-Mannheim-Distribution, Sprachen **deu + eng** mitwählen; Linux
  `apt-get install tesseract-ocr tesseract-ocr-deu`. Ohne Tesseract laufen
  alle anderen Prüfungen weiter, die OCR-Tests werden übersprungen.
- **pywin32** und SAP GUI Scripting (nur Windows, nur für den Echtbetrieb).
- Ohne Anzeige: `QT_QPA_PLATFORM=offscreen` setzen.

Mockdaten werden von den Tests selbst erzeugt (Testabschnitt in `drawing_checker.py`);
`python drawing_checker.py mockdata bauen` legt sie in `mockdata/out/` ab.

### 4. Wie hier gearbeitet wird (Konventionen, die zählen)

- **Sprache Deutsch** in Code, Docstrings, Findings, Commit-Messages.
- **Fachwissen gehört in YAML**, nicht in den Code. Neue Werkstoffe,
  Normen, Formulierungen in den YAML-Wissenspaketen ergänzen und
  `--check-rules` laufen lassen.
- **Jede neue Regel**: Code in `profiles.yaml` (eingebettet; `--export-rules`) registrieren,
  Severity dort pflegen, mindestens ein Positiv- und ein Negativtest, und
  im Regelkatalog dieses Dokuments eintragen (ein Test erzwingt das).
- **Unsicheres meldet „Prüfen", nie hart „Fehler".** Bei OCR-Grundlage
  wird jede Meldung automatisch heruntergestuft.
- **Vor jedem Push**: `python -m pytest drawing_checker.py -q` und `--check-rules`.

### 5. Womit Regeln kalibriert werden

`echt_quellen.zip` (nicht im Repository) enthält **84 echte, frei lizenzierte
Fertigungszeichnungen** (28 mit STEP) aus OreSat (CERN-OHL-S v2) und
ShapeOko (CC BY-SA 3.0) – Herkunft und Auswahlkriterien in
Abschnitt „Kalibrierzeichnungen: Herkunft“. Sie liegen bewusst als **ein** Archiv im
Repository; `python drawing_checker.py mockdata quellen` packt sie nach
`.echt_quellen/` aus (nicht im Repository), die Werkzeuge unten tun
das bei Bedarf von selbst. Bitte nicht wieder als Einzeldateien einchecken.

```bash
python drawing_checker.py mockdata fehler mockdata/echt_quellen /tmp/kal
python drawing_checker.py --headless --mock /tmp/kal \
    --excel /tmp/kal/Materialliste_Echt.xlsx --column C
python drawing_checker.py messen kalibrier /tmp/kal
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
| `python drawing_checker.py messen langlauf --count 200` | Läuft das Tool stundenlang stabil? Speicher, Platte, Zeit je Materialnummer |
| `python drawing_checker.py messen ocr` | Wie viel erkennt die OCR von einer gescannten Zeichnung wieder? |
| `python drawing_checker.py messen kalibrier <ordner>` | Wie viele Fehlalarme produzieren die Regeln? |
| `python drawing_checker.py --list-rules` | Was ist je Profil aktiv? |

Die Langlaufmessung hat zwei echte Speicherlecks gefunden (OpenCascade-
Leser und der interne Zwischenspeicher von PyMuPDF). Beide sind behoben;
wer an Abschnitt `ocr`, `step_compare.py` oder `annotate.py` arbeitet, sollte die
Messung danach wiederholen.

### 7. Was als Nächstes ansteht (Priorität)

1. **SAP-Durchstich mit echten Materialnummern** – alles andere ist
   nachrangig, solange das nicht läuft.
2. **Kalibrierung an echten Firmenzeichnungen**: 20–30 echte
   YMATDOCS-Pakete durchlaufen lassen, Fehlbefunde ansehen, Severities und
   Schwellen in `profiles.yaml` (eingebettet; `--export-rules`) nachziehen. Das bringt mehr als jede
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
  `release_memory()`.
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

> Die ursprüngliche Planung sah sechs Unterpakete vor. Heute ist das
> Programm eine Datei – die Gliederung steht oben unter
> [Gliederung von drawing_checker.py](#gliederung-von-drawing_checkerpy).

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
| Packaging | eine .py + Start.bat (venv) | Nicht-technische Nutzer; PyInstaller verworfen (Virenscanner, 300 MB) |
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
- Abschnitt `kern` entpackt das ZIP in einen Arbeitsordner je Materialnummer und
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

#### 4.4 Check-Engine (Abschnitt `regeln` + `pruef_*.py`)

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

1. Abschnitt `zeichnung` extrahiert Maßzahlen aus dem PDF-Textlayer
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


---

# Hinweise für Claude-Sessions

Internes Windows-Tool: prüft technische Zeichnungen je SAP-Materialnummer
(YMATDOCS-ZIP mit PDF + optional STEP) auf Normverstöße, fachliche
Widersprüche und Geometrie-Mismatch. GUI für nicht-technische Anwender.
Sprache im Code/UI: Deutsch (Docstrings, Findings, Commit-Messages).

**Das Repository besteht aus drei Dateien** – `drawing_checker.py`,
`Start.bat`, `README.md` – und das bleibt so. Neue Funktionen kommen in
den passenden Abschnitt von `drawing_checker.py`, neue Tests in den
Testabschnitt am Dateiende, neues Wissen in den Abschnitt
`wissenspakete`, Doku hierher. Keine neuen Dateien anlegen. Es gibt keine
CLAUDE.md mehr – dieser Abschnitt ist ihr Ersatz; beim Sitzungsstart
lesen.

## Kommandos

Siehe [Alle Aufrufe](#alle-aufrufe). Vor jedem Push:
`python -m pytest drawing_checker.py -q` und
`python drawing_checker.py --check-rules`.

## Architektur

Eine Datei, gegliedert in Abschnitte – siehe
[Gliederung von drawing_checker.py](#gliederung-von-drawing_checkerpy).

Wichtig dabei:

- **SAP wird nicht programmiert, sondern aufgezeichnet.** Abschnitt `sap_ablauf`
  liest den .vbs-Mitschnitt und spielt ihn ab (generische `call`/`set_prop`
  decken auch ALV-Grid-Methoden ab); Abschnitt `sap_ymatdocs` klammert
  Download-Überwachung und Statusauswertung darum. Ablaufdatei:
  `regeln/ymatdocs_flow.yaml`. Die nachgebaute Sitzung in
  Abschnitt `sap_ymatdocs` deckt Tests und `--sap-dry-run` ab.
  Checkliste für den Durchstich: README.md, Abschnitt „SAP-Durchstich".
- **Wissen gehört in die YAML-Wissenspakete** (Abschnitt `wissenspakete`:
  profiles, materials, norms, beschaffung) – NIE fachliche Listen im Code hartkodieren. YAML erweitern
  und `--check-rules` laufen lassen. Externe Overlays: Ordner `regeln/`
  neben der .exe bzw. `DRAWING_CHECKER_RULES`.
- **OCR** ist auf Zeichnungen getrimmt (400 dpi, Otsu, Deskew, PSM 11,
  90°-Durchgang für gedrehte Maßtexte, Wörterbücher aus, Nachkorrektur);
  jedes `Word` trägt eine Konfidenz, unsichere Zahlen werden kein Maß.
  Seitenweise: OCR nur für Seiten ohne Textlayer. Einstellungen über
  `DRAWING_CHECKER_OCR_*`, Güte messbar mit `python drawing_checker.py messen ocr`.
- **Ringschlüsse vermeiden**: `sap_sitzung` trägt die Adapter-Schnittstelle,
  `sap_ymatdocs` importiert nur in eine Richtung. Die `pruef_*`-Module
  greifen untereinander nur über träge Importe in Funktionen zu.

## Konventionen

- Jede neue Regel: Code (Schema GRUPPE.NAME) in `profiles.yaml` (Abschnitt `wissenspakete`) registrieren,
  Severity dort pflegen, mindestens 1 Positiv- + 1 Negativtest, Eintrag im
  Regelkatalog dieser README (ein Test erzwingt das).
- Unsicheres meldet `warning` („nicht nachweisbar/prüfen"), nie hart `error`.
- Findings mit `bbox` (PDF-Koordinaten) werden im Bild markiert.
- **Ein Modul, ein Namensraum.** Ein Test verbietet doppelt vergebene Namen
  auf oberster Ebene – daran ist beim Zusammenlegen ein verdeckter Regex
  aufgefallen. Neue Namen müssen eindeutig sein.
- Gemeinsame Testhelfer (`make_ctx`, `codes`, `make_config`, `FONT`, `ECHT`,
  `FIXTURE`) stehen einmal am Anfang des Testabschnitts (`conftest`).
- Mockdaten sind Test-Fixtures (je Lauf gebaut); echte Kalibrierzeichnungen
  liegen NICHT im Repository – siehe
  [Kalibrierzeichnungen](#kalibrierzeichnungen-herkunft).
- Vor jedem Push: `python -m pytest drawing_checker.py -q` und `--check-rules`.
- Regeln werden an den 84 echten Fremdzeichnungen kalibriert, nicht an
  Musterzeichnungen: `python drawing_checker.py mockdata fehler` + `--headless` +
  `python drawing_checker.py messen kalibrier`. Harte Meldungen auf den unveränderten
  Referenzen sind Fehlalarm-Verdacht.
- Speicher: OpenCascade und PyMuPDF geben nichts von selbst frei – nach
  großen Puffern `release_memory()` aufrufen und mit
  `python drawing_checker.py messen langlauf` gegenmessen.
- Übergabe an die nächste Sitzung: den Abschnitt „Übergabe" hier aktuell
  halten.
