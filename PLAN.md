# Drawing Checker – Planungsdokument

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
   - je Materialnummer: SAP-GUI-Report über Transaktion `YMATDOCS` (P11),
   - Zeichnung + STEP beschaffen,
   - Checks ausführen,
   - Screenshot der Zeichnung annotieren und ablegen,
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
│   └── models.py           # Datenklassen: MaterialJob, CheckResult, Finding
├── sap/
│   ├── session.py          # Verbindung, Session-Handling, Login P11
│   ├── ymatdocs.py         # Transaktionsablauf (aus dem .vbs portiert)
│   └── watchdog.py         # Absturz-Erkennung + automatischer Neustart
├── checks/
│   ├── base.py             # Check-Interface, Findings mit Koordinaten
│   ├── drawing_checks.py   # Fachliche Checks techn. Kommunikation
│   └── step_compare.py     # Geometrieabgleich Zeichnung vs. STEP
├── report/
│   ├── annotate.py         # Screenshot + Markierungen/Nummern (Pillow)
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
| Screenshot | SAP-Scripting `HardCopy` / Fensterscreenshot (`mss` als Fallback) | Zeichnung so, wie der Anwender sie sieht |
| Annotation | `Pillow` | Rechtecke/Nummern/Legende auf den Screenshot |
| STEP-Lesen | `cadquery-ocp` / `pythonocc-core` (OpenCascade) | STEP parsen, Maße/Bounding-Box/Volumen extrahieren |
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
- `ymatdocs.py` kapselt den kompletten Transaktionsablauf. **Der morgen erstellte
  .vbs-Mitschnitt ist die Referenz** – er wird mechanisch nach Python portiert
  (gleiche Element-IDs), ergänzt um Waits/Existenzprüfungen statt fixer Sleeps.
- Jeder Schritt mit Timeout und definierter Fehlerklasse:
  - *Material nicht gefunden / keine Zeichnung / kein STEP* → fachliches Finding,
    weiter mit nächster Nummer.
  - *Session tot / COM-Fehler / SAP-Fenster weg* → Watchdog-Fall.

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
`bbox` (Koordinaten auf dem Screenshot) ermöglicht die Annotation.

**a) Zeichnungs-Checks (technische Kommunikation / Vollständigkeit)** – Beispiele,
finale Regelliste kommt aus dem Fachbereich:
- Schriftfeld vollständig (Benennung, Zeichnungsnummer, Maßstab, Werkstoff,
  Freigabestatus, Änderungsindex)
- Allgemeintoleranzangabe vorhanden (z. B. ISO 2768 / ISO 22081)
- Oberflächenangaben, Kantenzustand (ISO 13715), Projektionsmethode
- Konsistenz Materialnummer/Zeichnungsnummer zwischen SAP-Stammdaten und Zeichnung

Die Regeln werden als **konfigurierbare Regelliste** (YAML) gebaut, damit der
Fachbereich Regeln je Materialgruppe schärfen/abschalten kann.

**b) STEP-Abgleich (`step_compare.py`)**
- STEP laden (OpenCascade), extrahieren: Bounding-Box, Volumen, ggf. markante Maße.
- Abgleich gegen die Sollwerte der Zeichnung/SAP-Stammdaten (Abmessungen, Gewicht
  über Dichte, sofern Werkstoff bekannt) mit konfigurierbarer Toleranz.
- Abweichung → Finding „Geometrie passt nicht zur Zeichnung – vermutlich falsche
  Konfiguration gespeichert".

### 4.5 Reporting (`report/`)

- **Screenshot-Annotation:** nummerierte Marker an den `bbox`-Positionen,
  Legende am Rand (Nr. → Findingtext), Ampelfarbe je Severity.
  Ablage: `Ergebnisse/<Lauf-Zeitstempel>/<Materialnummer>.png`.
- **Excel-Rückschrieb:** Ergebnis-Spalten werden rechts angefügt
  (Status, Anzahl Findings, Findingtexte, Link zum Screenshot).
  Original bleibt unangetastet – geschrieben wird in eine Kopie
  `<Dateiname>_geprüft.xlsx` (vermeidet Konflikte, wenn Datei geöffnet ist).

---

## 5. Offene Punkte (bitte klären)

1. **.vbs-Mitschnitt** von `YMATDOCS` → Grundlage für `sap/ymatdocs.py`
   (kommt morgen). Wichtig: Wie wird darin die Zeichnung angezeigt
   (SAP-Viewer? PDF-Download? DMS-Original öffnen?) und wie kommt das STEP-File
   raus (Download-Pfad)?
2. **Format der Zeichnung:** SAP-Viewer-Ansicht (nur Screenshot) oder liegt ein
   PDF/TIFF-Original vor? Davon hängt ab, ob die fachlichen Checks auf
   Textextraktion (PDF), OCR (Rasterbild) oder nur auf SAP-Metadaten laufen.
3. **Regelkatalog** für den fachlichen Check: Liste der Pflichtangaben und
   K.O.-Kriterien vom Fachbereich (je Materialgruppe unterschiedlich?).
4. **Sollwerte für den STEP-Abgleich:** Woher kommen die Referenzmaße –
   SAP-Stammdaten (Brutto-Maße/Gewicht), Zeichnungstext oder beides?
5. **Login P11:** SSO vorhanden oder Benutzer/Passwort nötig?
6. **Scripting freigeschaltet?** `sapgui/user_scripting = TRUE` auf P11 und im
   SAP-GUI-Client nötig – ggf. Basis-Team einbinden.

---

## 6. Meilensteine

| # | Meilenstein | Inhalt |
|---|---|---|
| M1 | Gerüst & GUI-Durchstich | Repo-Struktur, PySide6-Wizard, Excel laden, Spaltenwahl per Klick, Dummy-Lauf mit Fortschritt |
| M2 | SAP-Durchstich | .vbs → `ymatdocs.py`, eine Materialnummer end-to-end: Report ausführen, Screenshot ziehen |
| M3 | Robustheit | Watchdog, P11-Auto-Neustart, Resume-Zustand, Dauerlauf über echte Liste |
| M4 | Checks v1 | Regelkatalog umsetzen (konfigurierbar), STEP-Abgleich Bounding-Box/Volumen |
| M5 | Reporting | Annotation, Excel-Rückschrieb, Ergebnisordner, Abschlussdialog |
| M6 | Auslieferung | PyInstaller-.exe, Kurzanleitung mit Screenshots, Pilot mit einer Materialgruppe |

Reihenfolge bewusst: erst der SAP-Durchstich mit dem echten .vbs (M2), denn davon
hängen Zeichnungsformat und damit die Machbarkeit der fachlichen Checks (M4) ab.
