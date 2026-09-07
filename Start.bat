@echo off
rem ===================================================================
rem  Drawing Checker - Einrichtung, Menue und Start (Windows)
rem
rem  Doppelklick genuegt. Beim ersten Start wird alles Noetige
rem  eingerichtet (dauert einige Minuten), danach erscheint ein Menue,
rem  ueber das sich alles ohne Eingabe von Befehlen erledigen laesst.
rem
rem  Aufrufvarianten fuer Geuebte:
rem     Start.bat              Menue
rem     Start.bat pruefen      Installation und Regeln pruefen
rem     Start.bat neu          Umgebung verwerfen und neu aufbauen
rem     Start.bat --list-rules beliebige Programmoptionen durchreichen
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

rem ---------------------------------------------------------------- 0
rem Aus dem ZIP heraus gestartet? Windows entpackt dann in einen
rem Temp-Ordner, der spaeter geloescht wird - nichts bliebe erhalten.
echo %PROJEKT% | find /I "\Temp\" >nul
if not errorlevel 1 goto :aus_zip
>"%PROJEKT%schreibtest.tmp" echo x 2>nul
if not exist "%PROJEKT%schreibtest.tmp" goto :kein_schreibrecht
del "%PROJEKT%schreibtest.tmp" >nul 2>&1

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
    echo  Installiere die Programmbestandteile. Beim ersten Mal werden
    echo  einige hundert Megabyte geladen - bitte Geduld.
    echo [%DATE% %TIME%] pip install>>"%LOG%"
    "%PYEXE%" -m pip install --upgrade pip setuptools wheel >>"%LOG%" 2>&1
    echo  ... Grundprogramm
    "%PYEXE%" -m pip install -e "." >>"%LOG%" 2>&1
    if errorlevel 1 goto :fehler_pip

    rem Zusatzpakete einzeln: faellt eines aus, laeuft der Rest weiter.
    echo  ... SAP-Anbindung
    "%PYEXE%" -m pip install -e ".[sap]" >>"%LOG%" 2>&1
    if errorlevel 1 echo      HINWEIS: SAP-Anbindung ^(pywin32^) fehlt - nur Mockbetrieb moeglich.
    echo  ... Texterkennung fuer gescannte Zeichnungen
    "%PYEXE%" -m pip install -e ".[ocr]" >>"%LOG%" 2>&1
    if errorlevel 1 echo      HINWEIS: OCR-Paket fehlt - Scans werden nicht gelesen.
    echo  ... 3D-Auswertung der STEP-Dateien ^(grosses Paket, dauert^)
    "%PYEXE%" -m pip install -e ".[occ]" >>"%LOG%" 2>&1
    if errorlevel 1 echo      HINWEIS: 3D-Paket fehlt - Geometriepruefung nur eingeschraenkt.

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
if defined SELBSTTEST goto :selbsttest
if defined ARGS goto :durchreichen
goto :menu

rem ===================================================================
:menu
echo.
echo  ------------------------------------------------------------
echo    Was moechten Sie tun?
echo  ------------------------------------------------------------
echo    1  Zeichnungen pruefen ^(Programm starten^)
echo    2  SAP-Mitschnitt einlesen  ^(einmalig, .vbs aus SAP^)
echo    3  Trockenlauf ohne SAP     ^(prueft den eingelesenen Ablauf^)
echo    4  Eine Materialnummer testweise aus SAP holen
echo    5  Aktuelles SAP-Bild anzeigen ^(Diagnose bei Problemen^)
echo    6  Installation und Regeln pruefen
echo    7  Anleitung oeffnen
echo    8  Beenden
echo.
set "WAHL="
set /p "WAHL=Nummer eingeben und Enter druecken: "
if "%WAHL%"=="1" goto :m_start
if "%WAHL%"=="2" goto :m_vbs
if "%WAHL%"=="3" goto :m_trocken
if "%WAHL%"=="4" goto :m_test
if "%WAHL%"=="5" goto :m_dump
if "%WAHL%"=="6" goto :selbsttest
if "%WAHL%"=="7" goto :m_anleitung
if "%WAHL%"=="8" goto :ende
echo  Bitte eine Zahl von 1 bis 8 eingeben.
goto :menu

:m_start
echo.
echo  Das Programm wird gestartet. Bitte im Fenster die Excel-Datei
echo  waehlen und auf die Spalte mit den Materialnummern zeigen.
echo.
"%PYEXE%" -m drawing_checker.app
if errorlevel 1 call :fehlerhinweis
goto :menu

:m_vbs
echo.
echo  Ziehen Sie die .vbs-Datei aus dem Explorer in dieses Fenster
echo  ^(oder tippen Sie den Pfad^) und druecken Sie Enter.
echo  Ohne Eingabe geht es zurueck ins Menue.
set "VBS="
set /p "VBS=Datei: "
if not defined VBS goto :menu
set "VBS=%VBS:"=%"
if not exist "%VBS%" goto :m_vbs_fehlt
"%PYEXE%" -m drawing_checker.app --sap-import-vbs "%VBS%"
echo.
echo  Bitte oben pruefen: Ist die Materialnummer erkannt und der
echo  Download-Schritt richtig markiert? Danach Punkt 3 ^(Trockenlauf^).
pause
goto :menu

:m_vbs_fehlt
echo  Diese Datei gibt es nicht: %VBS%
pause
goto :menu

:m_trocken
echo.
set "MATNR="
set /p "MATNR=Materialnummer fuer den Trockenlauf (Enter = 4711): "
if not defined MATNR set "MATNR=4711"
"%PYEXE%" -m drawing_checker.app --sap-dry-run "%MATNR%"
pause
goto :menu

:m_test
echo.
set "MATNR="
set /p "MATNR=Echte Materialnummer aus SAP holen: "
if not defined MATNR goto :menu
echo  SAP muss offen und angemeldet sein.
"%PYEXE%" -m drawing_checker.app --sap-test "%MATNR%"
pause
goto :menu

:m_dump
echo.
echo  Zeigt den Aufbau des aktuellen SAP-Bildes. Vorher in SAP das
echo  Bild aufrufen, um das es geht.
"%PYEXE%" -m drawing_checker.app --sap-dump
pause
goto :menu

:m_anleitung
if exist "%PROJEKT%LIESMICH.txt" start "" notepad "%PROJEKT%LIESMICH.txt"
if not exist "%PROJEKT%LIESMICH.txt" echo  LIESMICH.txt wurde nicht gefunden.
goto :menu

:durchreichen
echo  Programm wird gestartet ...
echo.
"%PYEXE%" -m drawing_checker.app %ARGS%
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :fehler_lauf
goto :ende

rem ===================================================================
:selbsttest
echo.
echo  Pruefe die Installation ...
echo.
"%PYEXE%" -m drawing_checker.app --check-rules
echo.
"%PYEXE%" -m drawing_checker.app --ocr-check
echo.
"%PYEXE%" -m drawing_checker.app --sap-show-flow
echo.
if exist "%PROJEKT%tests" call :vollstaendiger_test
echo.
echo  Pruefung beendet.
pause
if defined SELBSTTEST goto :ende
goto :menu

:vollstaendiger_test
echo  Vollstaendiger Selbsttest dauert einige Minuten.
set "T="
set /p "T=Mit Enter starten, sonst eine Taste und Enter zum Ueberspringen: "
if defined T exit /b 0
"%PYEXE%" -m pip install -e ".[dev]" >>"%LOG%" 2>&1
"%PYEXE%" -m pytest tests -q
exit /b 0

:pruefe_python
rem Prueft, ob der uebergebene Aufruf ein Python ab 3.10 startet.
%~1 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
exit /b %ERRORLEVEL%

:fehlerhinweis
echo.
echo  Das Programm wurde mit einem Fehler beendet.
echo  Protokolle: Ordner "Ergebnisse" beim jeweiligen Lauf und
echo  %LOG%
pause
exit /b 0

:aus_zip
echo  Das Programm laeuft gerade AUS DEM ZIP-ARCHIV heraus.
echo.
echo  Bitte zuerst entpacken:
echo    1. Rechtsklick auf die ZIP-Datei
echo    2. "Alle extrahieren ..." waehlen, Ziel z. B. C:\Tools\DrawingChecker
echo    3. Im entpackten Ordner erneut auf Start.bat doppelklicken
echo.
echo  Aus dem Archiv heraus gehen alle Ergebnisse beim Schliessen verloren.
pause
endlocal
exit /b 1

:kein_schreibrecht
echo  In diesem Ordner darf nicht geschrieben werden:
echo    %PROJEKT%
echo.
echo  Bitte den Ordner an einen Ort mit Schreibrechten kopieren,
echo  zum Beispiel C:\Tools\DrawingChecker, und dort erneut starten.
pause
endlocal
exit /b 1

:kein_python
echo  Es wurde kein Python ab Version 3.10 gefunden.
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
echo  Start.bat            Menue ^(richtet bei Bedarf alles ein^)
echo  Start.bat pruefen    Installation und Regeln pruefen
echo  Start.bat neu        Umgebung verwerfen und neu aufbauen
echo  Start.bat ^<optionen^> Optionen an das Programm durchreichen, z. B.
echo                       Start.bat --sap-import-vbs ymatdocs.vbs
echo                       Start.bat --ocr-check
echo                       Start.bat --list-rules
echo.
endlocal
exit /b 0

:ende
endlocal
exit /b 0
