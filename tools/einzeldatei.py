"""Baut EINE einzige Datei: DrawingChecker_Setup.bat (selbstentpackend).

Noch einen Schritt weiter als das ZIP: Der Anwender bekommt eine Datei,
klickt sie an, und alles Weitere passiert von selbst – entpacken entfällt.

    python -m tools.einzeldatei [--ziel dist]

Aufbau der erzeugten Datei:

    Batch-Code (entpackt und startet)
    ::PAYLOAD::            <- Marke
    Base64 des ZIP-Pakets, eine Zeile je 76 Zeichen

Das Auspacken läuft über die Marke, nicht über gezählte Zeilen: Der
Batch-Teil sucht `::PAYLOAD::`, nimmt alles danach und dekodiert es.
Erste Wahl ist PowerShell (rechnet exakt, auf jedem Windows vorhanden),
Ersatzweg ist `certutil -decode` – und zwar mit beiden möglichen
Zeilenzählungen, weil `more +N` je nach Windows-Fassung um eine Zeile
abweicht. Entpackt wird mit `tar` (Windows 10 ab 1803), ersatzweise mit
PowerShell.

Ehrlich dazugesagt: Manche Virenscanner sehen selbstentpackende
Batch-Dateien kritisch. Wenn der Scanner meckert, ist das ZIP aus
`tools/paket_bauen.py` der unauffälligere Weg – beides ist eine Datei.
"""
from __future__ import annotations

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
rem  Erzeugt von tools/einzeldatei.py - nicht von Hand bearbeiten.
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


def bauen(ziel_dir: Path, quelle: Path | None = None) -> Path:
    """Erzeugt die selbstentpackende Datei aus dem ZIP-Paket."""
    from tools import paket_bauen

    ziel_dir.mkdir(parents=True, exist_ok=True)
    if quelle is None:
        quelle = paket_bauen.bauen(ziel_dir, mit_tests=False)

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


def pruefen(datei: Path) -> list[str]:
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ziel", type=Path, default=WURZEL / "dist")
    a = ap.parse_args(argv)

    datei = bauen(a.ziel)
    mb = datei.stat().st_size / (1024 * 1024)
    print(f"Gebaut: {datei}  ({mb:.1f} MB)")

    probleme = pruefen(datei)
    if probleme:
        print("\nPROBLEME:")
        for p in probleme:
            print(f"  - {p}")
        return 1
    print("Geprüft: Marke, Base64, ZIP und Regeln in Ordnung.")
    print("\nWeitergabe: DIESE EINE DATEI übertragen. Am Zielrechner")
    print("doppelklicken – sie entpackt sich selbst und richtet ein.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
