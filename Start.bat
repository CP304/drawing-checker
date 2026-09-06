@echo off
rem ===================================================================
rem  Drawing Checker - Start und Einrichtung (Windows)
rem
rem  Doppelklick genuegt. Beim ersten Start wird alles Noetige
rem  eingerichtet (dauert einige Minuten), danach startet das Programm
rem  sofort.
rem
rem  Aufrufvarianten:
rem     Start.bat              Programm starten (richtet bei Bedarf ein)
rem     Start.bat neu          Umgebung verwerfen und neu aufbauen
rem     Start.bat pruefen      Selbsttest laufen lassen
rem     Start.bat --sap-dump   beliebige Programmoptionen durchreichen
rem
rem  Hinweis fuer Entwickler: Diese Datei ist bewusst ohne Umlaute
rem  geschrieben. Batch-Dateien werden je nach Windows-Einstellung in
rem  unterschiedlichen Zeichensaetzen gelesen; Umlaute erscheinen dann
rem  als Buchstabensalat.
rem ===================================================================

setlocal EnableExtensions
title Drawing Checker
cd /d "%~dp0"

set "PROJEKT=%~dp0"
set "VENV=%PROJEKT%.venv"
set "PYEXE=%VENV%\Scripts\python.exe"
set "MARKER=%VENV%\eingerichtet.txt"
set "LOGDIR=%PROJEKT%logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1
set "LOG=%LOGDIR%\einrichtung.log"

set "ARGS=%*"
set "REBUILD="
set "SELBSTTEST="
rem Achtung: "if ... cmd1 & cmd2" fuehrt cmd2 IMMER aus - daher Klammern.
if /I "%~1"=="neu" (
    set "REBUILD=1"
    set "ARGS="
)
if /I "%~1"=="pruefen" (
    set "SELBSTTEST=1"
    set "ARGS="
)
if /I "%~1"=="hilfe" goto :hilfe
if /I "%~1"=="/?" goto :hilfe

echo.
echo  ============================================================
echo    Drawing Checker - Pruefung technischer Zeichnungen
echo  ============================================================
echo.

rem ---------------------------------------------------------------- 1
if defined REBUILD (
    echo  Umgebung wird neu aufgebaut ...
    if exist "%VENV%" rmdir /s /q "%VENV%"
)

rem ---------------------------------------------------------------- 2
rem Python suchen: erst der Launcher "py", dann "python".
set "BASEPY="
call :pruefe_python "py -3"
if not errorlevel 1 set "BASEPY=py -3"
if not defined BASEPY (
    call :pruefe_python "python"
    if not errorlevel 1 set "BASEPY=python"
)
if not defined BASEPY goto :kein_python

rem ---------------------------------------------------------------- 3
rem Eine vorhandene Umgebung kann unbrauchbar sein, wenn der Ordner
rem verschoben oder kopiert wurde - dann lieber neu aufbauen als raten.
if exist "%PYEXE%" (
    "%PYEXE%" -c "import sys" >nul 2>&1
    if errorlevel 1 (
        echo  Die vorhandene Umgebung ist unbrauchbar - wird neu aufgebaut.
        rmdir /s /q "%VENV%"
    )
)

if not exist "%PYEXE%" (
    echo  Richte die Arbeitsumgebung ein. Das dauert beim ersten Mal
    echo  einige Minuten - bitte das Fenster offen lassen.
    echo.
    echo [%DATE% %TIME%] venv anlegen>>"%LOG%"
    %BASEPY% -m venv "%VENV%" >>"%LOG%" 2>&1
    if errorlevel 1 goto :fehler_venv
    set "INSTALL=1"
)

rem ---------------------------------------------------------------- 4
rem Muss installiert werden? Nur wenn Marker fehlt oder pyproject neuer.
if not defined INSTALL (
    "%PYEXE%" -c "import pathlib,sys; m=pathlib.Path(r'%MARKER%'); p=pathlib.Path(r'%PROJEKT%pyproject.toml'); sys.exit(0 if m.exists() and m.read_text().strip()==str(p.stat().st_mtime_ns) else 1)" >nul 2>&1
    if errorlevel 1 set "INSTALL=1"
)
if not defined INSTALL (
    "%PYEXE%" -c "import drawing_checker" >nul 2>&1
    if errorlevel 1 set "INSTALL=1"
)

if defined INSTALL (
    echo  Installiere die Programmbestandteile ...
    echo [%DATE% %TIME%] pip install>>"%LOG%"
    "%PYEXE%" -m pip install --upgrade pip setuptools wheel >>"%LOG%" 2>&1
    "%PYEXE%" -m pip install -e "." >>"%LOG%" 2>&1
    if errorlevel 1 goto :fehler_pip

    rem Zusatzpakete einzeln: faellt eines aus, laeuft der Rest weiter.
    echo  ... SAP-Anbindung
    "%PYEXE%" -m pip install -e ".[sap]" >>"%LOG%" 2>&1
    if errorlevel 1 echo  HINWEIS: SAP-Anbindung ^(pywin32^) nicht installiert - nur Mockbetrieb moeglich.
    echo  ... Texterkennung fuer gescannte Zeichnungen
    "%PYEXE%" -m pip install -e ".[ocr]" >>"%LOG%" 2>&1
    if errorlevel 1 echo  HINWEIS: OCR-Paket nicht installiert - Scans werden nicht gelesen.
    echo  ... 3D-Auswertung der STEP-Dateien ^(grosses Paket, dauert^)
    "%PYEXE%" -m pip install -e ".[occ]" >>"%LOG%" 2>&1
    if errorlevel 1 echo  HINWEIS: 3D-Paket nicht installiert - Geometriepruefung nur eingeschraenkt.

    "%PYEXE%" -c "import pathlib; pathlib.Path(r'%MARKER%').write_text(str(pathlib.Path(r'%PROJEKT%pyproject.toml').stat().st_mtime_ns))" >nul 2>&1
    echo  Einrichtung abgeschlossen.
    echo.
)

rem ---------------------------------------------------------------- 5
rem Texterkennung ist ein eigenes Programm und wird nicht mitinstalliert.
where tesseract >nul 2>&1
if errorlevel 1 (
    echo  Hinweis: Tesseract ist nicht installiert. Gescannte Zeichnungen
    echo  ohne Textebene koennen dann nicht gelesen werden; alle anderen
    echo  Pruefungen laufen normal. Nachinstallieren:
    echo    https://github.com/UB-Mannheim/tesseract/wiki  ^(Sprachen deu + eng^)
    echo.
)

rem ---------------------------------------------------------------- 6
rem Wissenspakete pruefen - fehlerhafte YAML-Eintraege wuerden sonst
rem stillschweigend ignoriert.
"%PYEXE%" -m drawing_checker.app --check-rules >>"%LOG%" 2>&1
if errorlevel 1 (
    echo  ACHTUNG: In den Regeldateien steckt ein Fehler. Einzelheiten:
    echo    "%PYEXE%" -m drawing_checker.app --check-rules
    echo  Der Lauf startet trotzdem, fehlerhafte Eintraege werden ignoriert.
    echo.
)

rem ---------------------------------------------------------------- 7
if defined SELBSTTEST goto :selbsttest

echo  Programm wird gestartet ...
echo.
"%PYEXE%" -m drawing_checker.app %ARGS%
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :fehler_lauf
endlocal
exit /b 0

rem ===================================================================
:selbsttest
echo  Selbsttest laeuft ^(einige Minuten^) ...
"%PYEXE%" -m pip install -e ".[dev]" >>"%LOG%" 2>&1
"%PYEXE%" -m pytest tests -q
echo.
echo  Selbsttest beendet.
pause
endlocal
exit /b 0

:pruefe_python
rem Prueft, ob der uebergebene Aufruf ein Python ab 3.11 startet.
%~1 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
exit /b %ERRORLEVEL%

:kein_python
echo  Es wurde kein Python ab Version 3.11 gefunden.
echo.
echo  So beheben Sie das:
echo    1. Python von https://www.python.org/downloads/windows/ laden
echo       ^(oder in der Eingabeaufforderung: winget install Python.Python.3.12^)
echo    2. Bei der Installation "Add python.exe to PATH" ankreuzen
echo    3. Diese Datei erneut starten
echo.
echo  Falls Python ueber das Firmen-Softwarecenter verteilt wird,
echo  bitte dort anfordern.
pause
endlocal
exit /b 1

:fehler_venv
echo  Die Arbeitsumgebung konnte nicht angelegt werden.
echo  Einzelheiten stehen in: %LOG%
echo  Haeufige Ursache: fehlende Schreibrechte im Programmordner.
pause
endlocal
exit /b 1

:fehler_pip
echo  Die Installation ist fehlgeschlagen.
echo  Einzelheiten stehen in: %LOG%
echo.
echo  Haeufige Ursachen:
echo    - Kein Zugang zum Paketserver ^(Firmen-Proxy^). Dann in der
echo      Eingabeaufforderung setzen:  set HTTPS_PROXY=http://proxy:8080
echo    - Virenscanner blockiert das Entpacken. Ordner freigeben lassen.
echo    - Mit "Start.bat neu" laesst sich die Umgebung neu aufbauen.
pause
endlocal
exit /b 1

:fehler_lauf
echo.
echo  Das Programm wurde mit einem Fehler beendet ^(Code %RC%^).
echo  Das Laufprotokoll liegt im Ordner "Ergebnisse" beim jeweiligen Lauf,
echo  die Einrichtungsmeldungen in: %LOG%
pause
endlocal
exit /b %RC%

:hilfe
echo.
echo  Start.bat            Programm starten ^(richtet bei Bedarf ein^)
echo  Start.bat neu        Umgebung verwerfen und neu aufbauen
echo  Start.bat pruefen    Selbsttest laufen lassen
echo  Start.bat ^<optionen^> Optionen an das Programm durchreichen, z. B.
echo                       Start.bat --sap-import-vbs ymatdocs.vbs
echo                       Start.bat --ocr-check
echo                       Start.bat --list-rules
echo.
endlocal
exit /b 0
