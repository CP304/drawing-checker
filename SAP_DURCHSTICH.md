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

## 0. Mitschnitt erzeugen (in SAP, einmalig)

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
> (`_looks_like_not_found` in `sap/ymatdocs.py`).

---

## 1. Mitschnitt einlesen

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

## 2. Trockenlauf (ohne SAP)

```bat
python -m drawing_checker.app --sap-dry-run 10473215
```

Spielt den Ablauf gegen eine simulierte Session ab und beantwortet:
Werden alle Platzhalter aufgelöst? Landet die Materialnummer in einem
Feld? Öffnet der Auslöser den Datei-Dialog, und entsteht danach die Datei
am erwarteten Ort? Rückgabewert 0 = in Ordnung.

## 3. Einzeltest gegen echtes SAP

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

## 4. Dauerlauf

```bat
python -m drawing_checker.app            # GUI, Standardweg für Anwender
```

Ablauf-Datei wird automatisch gefunden (`regeln\ymatdocs_flow.yaml`);
abweichender Pfad über `--sap-flow`. Der Lauf ist wiederaufnehmbar:
Abbruch und Neustart setzen an der letzten offenen Materialnummer an.

---

## Was im Dauerlauf automatisch abgefangen wird

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

## Wenn etwas klemmt

- **„Element … nicht gefunden"** → Bild sieht anders aus als bei der
  Aufzeichnung. `--sap-dump` zeigt das aktuelle Bild; ID im YAML
  korrigieren oder Schritt `optional: true` setzen.
- **Ablauf hängt am Datei-Dialog** → prüfen, ob der Dialog wirklich
  `wnd[1]` ist (bei manchen Downloads `wnd[2]`); IDs im YAML anpassen.
- **Kein Download erkannt, obwohl die Datei da ist** → Ordner in
  `sap/download.py::default_watch_dirs` ergänzen oder im Datei-Dialog den
  Zielordner erzwingen (`{target_dir}`).
- **Scripting-Hinweisdialog erscheint bei jedem Aufruf** → SAP-GUI-Option
  aus Schritt 0.2 abschalten.
- **„pywin32 fehlt"** → `pip install pywin32` (nur Windows).

## Aufbau der SAP-Schicht (zum Nachlesen)

| Datei | Aufgabe |
|---|---|
| `sap/vbs_parser.py` | .vbs → Ablauf, erkennt Transaktion, Materialfeld, Dialogfelder, Download-Auslöser |
| `sap/script_flow.py` | Ablaufmodell + Player; `call`/`set_prop` bilden **jede** Scripting-Anweisung ab (auch ALV-Grid) |
| `sap/ymatdocs.py` | Ablauf je Materialnummer, Statusauswertung, Notnagel-Ablauf |
| `sap/session.py` | COM-Anbindung an P11, Wiederverwendung bestehender Sitzungen |
| `sap/watchdog.py` | Neustart von SAP Logon nach Absturz |
| `sap/popups.py` | Dialogbehandlung |
| `sap/download.py` | Erkennung der fertigen ZIP-Datei |
| `sap/diagnostics.py` | Elementbaum, Screenshot, Fehlerbericht |
| `sap/fake_session.py` | simulierte Session für Trockenlauf und Tests |
