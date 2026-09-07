"""Prüft das Verteilpaket: eine ZIP-Datei, die am Zielrechner reicht.

Der Anwenderrechner bekommt genau eine Datei. Fehlt darin ein
Wissenspaket oder das Startskript, merkt man es erst dort – deshalb wird
das Archiv hier gebaut und gegengeprüft.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from tools import paket_bauen

WURZEL = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def archiv(tmp_path_factory) -> Path:
    ziel = tmp_path_factory.mktemp("paket")
    return paket_bauen.bauen(ziel, mit_tests=False)


def namen(archiv: Path) -> set[str]:
    with zipfile.ZipFile(archiv) as zf:
        return set(zf.namelist())


def test_alles_liegt_in_einem_ordner(archiv):
    """Beim Entpacken darf nichts verstreut im Zielordner landen."""
    assert all(n.startswith("DrawingChecker/") for n in namen(archiv))


@pytest.mark.parametrize("datei", [
    "Start.bat", "LIESMICH.txt", "pyproject.toml", "ANLEITUNG.md",
    "SAP_DURCHSTICH.md", "REGELKATALOG.md",
    "drawing_checker/app.py",
    "drawing_checker/gui.py",
    "drawing_checker/sap_ymatdocs.py",
    "drawing_checker/rules/profiles.yaml",
    "drawing_checker/rules/materials.yaml",
    "drawing_checker/rules/norms.yaml",
    "drawing_checker/rules/beschaffung.yaml",
])
def test_pflichtdateien_enthalten(archiv, datei):
    assert f"DrawingChecker/{datei}" in namen(archiv)


def test_ballast_bleibt_draussen(archiv):
    """Kalibrierzeichnungen (25 MB) und Caches gehören nicht ins Paket."""
    for n in namen(archiv):
        assert "echt_quellen" not in n
        assert "__pycache__" not in n and not n.endswith(".pyc")
        assert "/.venv/" not in n
    assert archiv.stat().st_size < 5 * 1024 * 1024, "Paket unerwartet groß"


def test_archiv_ist_lesbar_und_vollstaendig(archiv):
    """Baut, entpackt und lädt die Wissenspakete im entpackten Stand."""
    assert paket_bauen.pruefen(archiv) == []


def test_mit_tests_enthaelt_die_testsuite(tmp_path):
    voll = paket_bauen.bauen(tmp_path, mit_tests=True)
    inhalt = namen(voll)
    assert "DrawingChecker/tests/test_e2e.py" in inhalt
    assert "DrawingChecker/mockdata/generate.py" in inhalt


# ------------------------------------------------- Einzeldatei (self-extract)
def test_einzeldatei_enthaelt_ein_gueltiges_paket(tmp_path):
    """Die selbstentpackende .bat muss ein brauchbares ZIP tragen."""
    from tools import einzeldatei

    datei = einzeldatei.bauen(tmp_path)
    assert datei.name == "DrawingChecker_Setup.bat"
    assert einzeldatei.pruefen(datei) == []


def test_einzeldatei_hat_marke_und_windows_zeilenenden(tmp_path):
    from tools import einzeldatei

    datei = einzeldatei.bauen(tmp_path)
    roh = datei.read_bytes()
    assert b"::PAYLOAD::\r\n" in roh
    assert roh.startswith(b"@echo off\r\n")
    # Der Batch-Teil darf die Nutzlast nie ausfuehren. Getrennt wird an der
    # Markenzeile, nicht am ersten Vorkommen - die Marke steht auch im
    # PowerShell-Aufruf des Kopfes.
    kopf = roh.split(b"\r\n::PAYLOAD::\r\n")[0].decode("ascii")
    assert "exit /b 0" in kopf
    assert kopf.count("::PAYLOAD::") >= 1        # Suche im Kopf vorhanden


def test_einzeldatei_nutzlast_ist_das_paket(tmp_path):
    """Was drinsteckt, ist genau das gebaute ZIP."""
    import zipfile

    from tools import einzeldatei, paket_bauen

    zip_pfad = paket_bauen.bauen(tmp_path, mit_tests=False)
    datei = einzeldatei.bauen(tmp_path, quelle=zip_pfad)
    assert einzeldatei.nutzlast(datei) == zip_pfad.read_bytes()
    with zipfile.ZipFile(zip_pfad) as zf:
        assert "DrawingChecker/Start.bat" in zf.namelist()


# ------------------------------------------- Kalibrierzeichnungen als Archiv
def test_kalibrierzeichnungen_liegen_als_ein_archiv():
    """Über hundert Einzeldateien im Repo waren unübersichtlich."""
    from mockdata import quellen

    assert quellen.ARCHIV.is_file()
    pdf, step = quellen.anzahl()
    assert pdf >= 80 and step >= 25


def test_zeichnungen_werden_ausgepackt(tmp_path):
    from mockdata.quellen import zeichnungen

    ordner = zeichnungen(ziel=tmp_path / "raus")
    assert len(list(ordner.glob("*.pdf"))) >= 80
    # Zweiter Aufruf packt nicht erneut aus.
    marke = (ordner / ".ausgepackt").stat().st_mtime_ns
    zeichnungen(ziel=tmp_path / "raus")
    assert (ordner / ".ausgepackt").stat().st_mtime_ns == marke
