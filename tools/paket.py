"""Baut die Auslieferung: ein ZIP und eine selbstentpackende Datei.

    python -m tools.paket            beide bauen und pruefen
    python -m tools.paket --nur zip  nur DrawingChecker.zip
    python -m tools.paket --nur bat  nur DrawingChecker_Setup.bat

Beide Wege liefern dasselbe Programm in EINER Datei. Das ZIP ist der
unauffaellige Weg (manche Virenscanner mustern selbstentpackende
Batch-Dateien), die .bat der bequeme: Doppelklick genuegt.
"""
from __future__ import annotations

# ======================================================================
# paket_bauen
# ======================================================================
# Baut EINE ZIP-Datei zum Verteilen auf den Anwenderrechner.
#
# Hintergrund: Der Zielrechner bekommt die Dateien über einen Kanal mit
# Begrenzung der Dateianzahl. Deshalb geht alles in ein einziges Archiv –
# entpacken, `Start.bat` doppelklicken, fertig.
#
#     python -m tools.paket_bauen [--ziel dist] [--mit-tests]
#
# Enthalten ist alles, was am Zielrechner gebraucht wird: das Programm samt
# Wissenspaketen, das Startskript, die Anleitungen. NICHT enthalten sind die
# Kalibrierzeichnungen (25 MB Testmaterial), Entwicklungsdateien und alles,
# was sich am Zielrechner ohnehin neu bildet (virtuelle Umgebung, Caches).
#
# Das Archiv wird nach dem Bauen selbst geprüft: Sind alle Pflichtdateien
# drin, ist Start.bat auf oberster Ebene, lässt sich das Programm aus dem
# entpackten Stand heraus importieren?
import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
# Alles liegt im Archiv unter EINEM Ordner. Dann landet beim Entpacken
# nichts verstreut im Zielordner, egal welche Variante der Anwender waehlt.
ORDNER_IM_ARCHIV = "DrawingChecker"

# Was ins Paket gehört. Reihenfolge = Reihenfolge im Archiv.
PFLICHT_DATEIEN = [
    "Start.bat",
    "LIESMICH.txt",
    "README.md",
    "pyproject.toml",
]
ORDNER = ["drawing_checker"]
ORDNER_MIT_TESTS = ["drawing_checker", "tests", "mockdata"]

# Diese Muster fliegen raus (Caches, Entwicklungsreste, Testmaterial).
AUSSCHLUSS = (
    "__pycache__", ".pyc", ".pyo", ".pytest_cache", ".git",
    "echt_quellen", "mockdata/out", "Ergebnisse", ".venv", "logs/",
)


def gehoert_dazu(pfad: Path) -> bool:
    text = pfad.as_posix()
    return not any(muster in text for muster in AUSSCHLUSS)


def sammle(mit_tests: bool) -> list[tuple[Path, str]]:
    """(Quelldatei, Name im Archiv) für alles, was mitkommt."""
    dateien: list[tuple[Path, str]] = []
    for name in PFLICHT_DATEIEN:
        quelle = WURZEL / name
        if not quelle.is_file():
            raise SystemExit(f"Pflichtdatei fehlt: {name}")
        dateien.append((quelle, name))
    for ordner in (ORDNER_MIT_TESTS if mit_tests else ORDNER):
        basis = WURZEL / ordner
        if not basis.is_dir():
            continue
        for pfad in sorted(basis.rglob("*")):
            if pfad.is_file() and gehoert_dazu(pfad.relative_to(WURZEL)):
                dateien.append((pfad, pfad.relative_to(WURZEL).as_posix()))
    return dateien


def zip_bauen(ziel_dir: Path, mit_tests: bool = False) -> Path:
    dateien = sammle(mit_tests)
    ziel_dir.mkdir(parents=True, exist_ok=True)
    ziel = ziel_dir / "DrawingChecker.zip"
    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for quelle, name in dateien:
            zf.write(quelle, f"{ORDNER_IM_ARCHIV}/{name}")
    return ziel


def zip_pruefen(archiv: Path) -> list[str]:
    """Das gebaute Archiv gegenprüfen – lieber hier scheitern als morgen."""
    probleme: list[str] = []
    with zipfile.ZipFile(archiv) as zf:
        namen = set(zf.namelist())
        kaputt = zf.testzip()
    if kaputt:
        probleme.append(f"Archiv beschädigt bei {kaputt}")
    for kurz in ("Start.bat", "LIESMICH.txt", "README.md", "pyproject.toml",
                 "drawing_checker/app.py",
                 "drawing_checker/rules/profiles.yaml",
                 "drawing_checker/rules/materials.yaml",
                 "drawing_checker/rules/norms.yaml",
                 "drawing_checker/rules/beschaffung.yaml"):
        pflicht = f"{ORDNER_IM_ARCHIV}/{kurz}"
        if pflicht not in namen:
            probleme.append(f"fehlt im Archiv: {pflicht}")
    if any(n.startswith(("/", "\\")) or ".." in n for n in namen):
        probleme.append("verdächtige Pfade im Archiv")
    if any("__pycache__" in n or n.endswith(".pyc") for n in namen):
        probleme.append("Cache-Dateien im Archiv")

    # Entpacken und das Programm ohne Installation importieren:
    # findet fehlende Wissenspakete und Tippfehler in den YAML-Dateien.
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(archiv) as zf:
            zf.extractall(tmp)
        ergebnis = subprocess.run(
            [sys.executable, "-m", "drawing_checker.app", "--check-rules"],
            cwd=Path(tmp) / ORDNER_IM_ARCHIV, capture_output=True, text=True)
        if ergebnis.returncode != 0:
            probleme.append("Regelprüfung im entpackten Stand fehlgeschlagen: "
                            + (ergebnis.stdout + ergebnis.stderr)[-400:])
        elif "in Ordnung" not in ergebnis.stdout:
            probleme.append("Regelprüfung meldet Probleme:\n"
                            + ergebnis.stdout[-400:])
    return probleme




# ======================================================================
# einzeldatei
# ======================================================================
# Baut EINE einzige Datei: DrawingChecker_Setup.bat (selbstentpackend).
#
# Noch einen Schritt weiter als das ZIP: Der Anwender bekommt eine Datei,
# klickt sie an, und alles Weitere passiert von selbst – entpacken entfällt.
#
#     python -m tools.paket --nur bat
#
# Aufbau der erzeugten Datei:
#
#     Batch-Code (entpackt und startet)
#     ::PAYLOAD::            <- Marke
#     Base64 des ZIP-Pakets, eine Zeile je 76 Zeichen
#
# Das Auspacken läuft über die Marke, nicht über gezählte Zeilen: Der
# Batch-Teil sucht `::PAYLOAD::`, nimmt alles danach und dekodiert es.
# Erste Wahl ist PowerShell (rechnet exakt, auf jedem Windows vorhanden),
# Ersatzweg ist `certutil -decode` – und zwar mit beiden möglichen
# Zeilenzählungen, weil `more +N` je nach Windows-Fassung um eine Zeile
# abweicht. Entpackt wird mit `tar` (Windows 10 ab 1803), ersatzweise mit
# PowerShell.
#
# Ehrlich dazugesagt: Manche Virenscanner sehen selbstentpackende
# Batch-Dateien kritisch. Wenn der Scanner meckert, ist das ZIP aus
# das ZIP der unauffälligere Weg – beides ist eine Datei.
import argparse
import base64
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
MARKE = "::PAYLOAD::"

KOPF = r"""@echo off
rem ===================================================================
rem  Drawing Checker - Einzeldatei zum Verteilen
rem
rem  Diese Datei enthaelt das komplette Programm. Doppelklick genuegt:
rem  Sie entpackt sich in einen Ordner neben sich und startet dann die
rem  Einrichtung. Es wird nichts in Windows installiert und nichts in
rem  der Registry geaendert - alles bleibt in dem einen Ordner.
rem
rem  Erzeugt von tools/paket.py - nicht von Hand bearbeiten.
rem ===================================================================
setlocal EnableExtensions
title Drawing Checker - Einrichtung
cd /d "%~dp0"

set "ZIEL=%~dp0DrawingChecker"
set "ZIP=%TEMP%\dc_paket_%RANDOM%.zip"
set "B64=%TEMP%\dc_paket_%RANDOM%.b64"

echo.
echo  ============================================================
echo    Drawing Checker - Pruefung technischer Zeichnungen
echo  ============================================================
echo.
if exist "%ZIEL%\Start.bat" (
    echo  Das Programm liegt bereits hier und wird aktualisiert:
) else (
    echo  Das Programm wird entpackt nach:
)
echo    %ZIEL%
echo.
echo  Bitte warten ...

rem --- 1. Weg: PowerShell rechnet die Marke exakt aus.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$z=Get-Content -LiteralPath '%~f0'; $i=[Array]::IndexOf($z,'::PAYLOAD::'); if($i -lt 0){exit 1}; [IO.File]::WriteAllBytes('%ZIP%',[Convert]::FromBase64String(-join $z[($i+1)..($z.Count-1)]))" >nul 2>&1

rem --- 2. Weg: certutil. "more +N" zaehlt je nach Windows-Fassung
rem     unterschiedlich, deshalb beide Varianten versuchen.
if not exist "%ZIP%" call :certutil_weg
if not exist "%ZIP%" goto :fehler_decode

if not exist "%ZIEL%" mkdir "%ZIEL%" >nul 2>&1
tar -xf "%ZIP%" -C "%~dp0" >nul 2>&1
if not exist "%ZIEL%\Start.bat" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
     "Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%~dp0' -Force" >nul 2>&1
)
del "%ZIP%" >nul 2>&1
if not exist "%ZIEL%\Start.bat" goto :fehler_entpacken

echo  Entpackt. Die Einrichtung startet jetzt.
echo.
cd /d "%ZIEL%"
call "%ZIEL%\Start.bat"
endlocal
exit /b 0

:certutil_weg
for /f "delims=:" %%z in ('findstr /n /b /c:"::PAYLOAD::" "%~f0"') do set "MARKE=%%z"
if not defined MARKE exit /b 1
call :entziffern %MARKE%
if exist "%ZIP%" exit /b 0
set /a NACH=%MARKE%+1
call :entziffern %NACH%
exit /b 0

:entziffern
more +%1 "%~f0" > "%B64%" 2>nul
certutil -decode "%B64%" "%ZIP%" >nul 2>&1
del "%B64%" >nul 2>&1
if not exist "%ZIP%" exit /b 1
rem Zu kleine Dateien sind Bruchstuecke - dann war die Zeilenzahl falsch.
for %%g in ("%ZIP%") do if %%~zg LSS 20000 del "%ZIP%" >nul 2>&1
exit /b 0

:fehler_decode
echo.
echo  Das eingebettete Paket liess sich nicht auspacken.
echo.
echo  Haeufige Ursache: Die Datei wurde beim Uebertragen veraendert
echo  (z. B. von einem Mailsystem). Bitte erneut uebertragen - oder die
echo  ZIP-Fassung DrawingChecker.zip verwenden.
pause
endlocal
exit /b 1

:fehler_entpacken
echo.
echo  Das Paket liess sich nicht entpacken.
echo  Bitte die ZIP-Fassung DrawingChecker.zip verwenden: entpacken und
echo  darin Start.bat doppelklicken.
pause
endlocal
exit /b 1

rem Ab hier folgt das Paket als Base64 - nicht bearbeiten.
::PAYLOAD::
"""


def bat_bauen(ziel_dir: Path, quelle: Path | None = None) -> Path:
    """Erzeugt die selbstentpackende Datei aus dem ZIP-Paket."""
    ziel_dir.mkdir(parents=True, exist_ok=True)
    if quelle is None:
        quelle = zip_bauen(ziel_dir, mit_tests=False)

    b64 = base64.b64encode(quelle.read_bytes()).decode("ascii")
    zeilen = [b64[i:i + 76] for i in range(0, len(b64), 76)]

    ziel = ziel_dir / "DrawingChecker_Setup.bat"
    # Windows-Zeilenenden: cmd.exe und more/findstr rechnen damit.
    with open(ziel, "w", encoding="ascii", newline="\r\n") as fh:
        fh.write(KOPF)
        fh.write("\n".join(zeilen))
        fh.write("\n")
    return ziel


def nutzlast(datei: Path) -> bytes:
    """Holt das eingebettete ZIP heraus – wie es der Batch-Teil tut."""
    text = datei.read_bytes().decode("ascii", errors="replace")
    zeilen = text.split("\r\n")
    if MARKE not in zeilen:
        raise ValueError("Marke ::PAYLOAD:: fehlt")
    ab = zeilen.index(MARKE) + 1
    return base64.b64decode("".join(zeilen[ab:]).strip(), validate=True)


def bat_pruefen(datei: Path) -> list[str]:
    """Prüft die Einzeldatei so weit, wie es ohne Windows geht."""
    probleme: list[str] = []
    roh = datei.read_bytes()
    if b"\r\n" not in roh:
        probleme.append("keine Windows-Zeilenenden")
    if b"::PAYLOAD::" not in roh:
        probleme.append("Marke ::PAYLOAD:: fehlt")
        return probleme
    try:
        daten = nutzlast(datei)
    except Exception as exc:
        probleme.append(f"Nutzlast nicht lesbar: {exc}")
        return probleme

    with tempfile.TemporaryDirectory() as tmp:
        zip_pfad = Path(tmp) / "paket.zip"
        zip_pfad.write_bytes(daten)
        try:
            with zipfile.ZipFile(zip_pfad) as zf:
                namen = zf.namelist()
                if zf.testzip():
                    probleme.append("ZIP beschädigt")
                zf.extractall(tmp)
        except zipfile.BadZipFile as exc:
            probleme.append(f"kein gültiges ZIP: {exc}")
            return probleme
        if "DrawingChecker/Start.bat" not in namen:
            probleme.append("Start.bat fehlt im eingebetteten Paket")
        ergebnis = subprocess.run(
            [sys.executable, "-m", "drawing_checker.app", "--check-rules"],
            cwd=Path(tmp) / "DrawingChecker", capture_output=True, text=True)
        if "in Ordnung" not in ergebnis.stdout:
            probleme.append("Regelprüfung im entpackten Stand fehlgeschlagen")
    return probleme




# ======================================================================
# Einstieg
# ======================================================================
def main(argv: list[str] | None = None) -> int:
    """Baut ZIP und Einzeldatei - die .bat aus genau demselben ZIP."""
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ziel", type=Path, default=WURZEL / "dist")
    ap.add_argument("--nur", choices=["zip", "bat"],
                    help="nur eine der beiden Fassungen bauen")
    ap.add_argument("--mit-tests", action="store_true", dest="mit_tests",
                    help="Tests und Mockdaten mitpacken (Selbsttest am "
                         "Zielrechner)")
    a = ap.parse_args(argv)

    fehler = 0
    zip_pfad = None
    if a.nur != "bat":
        zip_pfad = zip_bauen(a.ziel, a.mit_tests)
        mb = zip_pfad.stat().st_size / (1024 * 1024)
        anz = len(zipfile.ZipFile(zip_pfad).namelist())
        print(f"Gebaut: {zip_pfad}  ({mb:.1f} MB, {anz} Dateien im Archiv)")
        probleme = zip_pruefen(zip_pfad)
        if probleme:
            print("\nPROBLEME:")
            for p in probleme:
                print(f"  - {p}")
            fehler = 1
        else:
            print("Archiv geprueft: vollstaendig, entpackbar, Regeln laden sauber.")

    if a.nur != "zip":
        datei = bat_bauen(a.ziel, quelle=zip_pfad)
        mb = datei.stat().st_size / (1024 * 1024)
        print(f"Gebaut: {datei}  ({mb:.1f} MB)")
        probleme = bat_pruefen(datei)
        if probleme:
            print("\nPROBLEME:")
            for p in probleme:
                print(f"  - {p}")
            fehler = 1
        else:
            print("Einzeldatei geprueft: Marke, Base64, ZIP und Regeln in Ordnung.")

    if not fehler:
        print("\nWeitergabe: EINE Datei uebertragen. DrawingChecker_Setup.bat")
        print("doppelklicken - oder DrawingChecker.zip entpacken und darin")
        print("Start.bat doppelklicken.")
    return fehler


if __name__ == "__main__":
    import sys

    sys.exit(main())
