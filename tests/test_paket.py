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
    "drawing_checker/gui/main_window.py",
    "drawing_checker/sap/ymatdocs.py",
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
