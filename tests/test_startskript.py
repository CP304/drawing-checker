"""Prüft Start.bat auf die klassischen Batch-Fallen.

Unter Linux lässt sich eine .bat-Datei nicht ausführen; die typischen
Fehler sind aber statisch erkennbar und haben es in sich – eine unescapte
Klammer in einem `if (...)`-Block bricht die Datei mitten im Lauf ab, und
das merkt man erst beim Anwender.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

BAT = Path(__file__).resolve().parent.parent / "Start.bat"
TEXT = BAT.read_text(encoding="ascii", errors="strict")
ZEILEN = TEXT.splitlines()


def test_datei_vorhanden_und_reines_ascii():
    """Umlaute in .bat-Dateien werden je nach Codepage zu Buchstabensalat."""
    assert BAT.is_file()
    TEXT.encode("ascii")          # wirft bei Umlauten


def _klammer_tiefe(zeile: str, tiefe: int) -> int:
    """Blocktiefe fortschreiben: Anführungszeichen und ^-Escapes beachten."""
    in_string = False
    i = 0
    while i < len(zeile):
        c = zeile[i]
        if c == "^":
            i += 2                # nächstes Zeichen ist escaped
            continue
        if c == '"':
            in_string = not in_string
        elif not in_string and c == "(":
            tiefe += 1
        elif not in_string and c == ")":
            tiefe -= 1
        i += 1
    return tiefe


def test_bloecke_sind_ausgeglichen():
    tiefe = 0
    for nr, zeile in enumerate(ZEILEN, start=1):
        if zeile.strip().lower().startswith("rem "):
            continue
        tiefe = _klammer_tiefe(zeile, tiefe)
        assert tiefe >= 0, f"Zeile {nr}: schließende Klammer zu viel"
    assert tiefe == 0, "am Dateiende ist ein Block noch offen"


def test_alle_sprungziele_existieren():
    labels = {z.strip().lstrip(":").lower()
              for z in ZEILEN if z.strip().startswith(":")}
    ziele = {m.group(1).lower()
             for m in re.finditer(r"goto\s+:?(\w+)", TEXT, re.IGNORECASE)}
    fehlend = ziele - labels
    assert not fehlend, f"Sprungziele ohne Label: {sorted(fehlend)}"


def test_keine_verzoegerte_expansion_noetig():
    """Variablen, die in einem Block gesetzt UND gelesen werden.

    Ohne `setlocal EnableDelayedExpansion` liest %VAR% dort den ALTEN
    Wert – der Klassiker unter den Batch-Fehlern.
    """
    tiefe = 0
    gesetzt_im_block: set[str] = set()
    probleme: list[str] = []
    for nr, zeile in enumerate(ZEILEN, start=1):
        if zeile.strip().lower().startswith("rem "):
            continue
        vorher = tiefe
        tiefe = _klammer_tiefe(zeile, tiefe)
        if vorher == 0 and tiefe > 0:
            gesetzt_im_block = set()
        if tiefe > 0 or vorher > 0:
            for m in re.finditer(r'set\s+"?(\w+)=', zeile, re.IGNORECASE):
                gesetzt_im_block.add(m.group(1).lower())
            for m in re.finditer(r"%(\w+)%", zeile):
                if m.group(1).lower() in gesetzt_im_block:
                    probleme.append(f"Zeile {nr}: %{m.group(1)}%")
        if tiefe == 0:
            gesetzt_im_block = set()
    assert not probleme, ("verzögerte Expansion nötig oder Zuweisung "
                          f"umstellen: {probleme}")


def test_ohne_argument_wird_nichts_durchgereicht():
    """`Start.bat neu`/`pruefen` dürfen nicht an das Programm gehen."""
    assert 'if /I "%~1"=="neu" (' in TEXT
    assert re.search(r'if /I "%~1"=="neu" \(\s*\n\s*set "REBUILD=1"\s*\n\s*'
                     r'set "ARGS="', TEXT)


@pytest.mark.parametrize("schritt", [
    "-m venv",                       # Umgebung anlegen
    "-m pip install -e \".\"",       # Programm installieren
    '.[occ]', '.[ocr]', '.[sap]',    # Zusatzpakete
    "-m drawing_checker.app --check-rules",
    "-m drawing_checker.app %ARGS%",  # Start
    "-m pytest tests -q",            # Selbsttest
])
def test_wesentliche_schritte_vorhanden(schritt):
    assert schritt in TEXT, f"Schritt fehlt im Startskript: {schritt}"


def _labelblock(label: str) -> str:
    """Text ab der Label-DEFINITION (nicht ab dem goto) bis exit /b."""
    m = re.search(rf"^:{label}\s*$", TEXT, re.MULTILINE)
    assert m, f"Label :{label} fehlt"
    return TEXT[m.end():].split("exit /b", 1)[0]


def test_fehlerwege_halten_das_fenster_offen():
    """Bei Doppelklick darf das Fenster im Fehlerfall nicht zuklappen."""
    for label in ("kein_python", "fehler_venv", "fehler_pip", "fehler_lauf"):
        assert "pause" in _labelblock(label), \
            f"{label}: kein pause vor dem Beenden"


def test_hilfetext_nennt_alle_varianten():
    hilfe = _labelblock("hilfe")
    for variante in ("neu", "pruefen", "--sap-import-vbs"):
        assert variante in hilfe
