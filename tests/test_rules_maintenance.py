"""Manuelle Pflege der Wissenspakete: externer regeln/-Ordner + Validierung."""
import os
from pathlib import Path

import pytest

from drawing_checker import regeln as base
from drawing_checker.regeln import validate_rules


@pytest.fixture()
def extern_rules(tmp_path, monkeypatch):
    d = tmp_path / "regeln"
    d.mkdir()
    monkeypatch.setenv("DRAWING_CHECKER_RULES", str(d))
    return d


def reload_materials():
    from drawing_checker import pruef_werkstoff as materials

    materials.MATERIALS = materials._load_materials()
    materials.OBSOLETE_NORMS = materials._load_obsolete_norms()
    return materials


def test_builtin_rules_are_valid():
    issues, stats = validate_rules()
    assert issues == [], "\n".join(map(str, issues))
    assert stats["materialien"] >= 60
    assert stats["normen"] >= 20
    assert stats["profile"] >= 3


def test_external_dir_is_loaded(extern_rules):
    (extern_rules / "materials_firma.yaml").write_text(
        "materials:\n"
        "  - {name: Hauswerkstoff X1, patterns: ['\\\\bHW-X1\\\\b'],\n"
        "     category: baustahl, weldable: ja}\n", encoding="utf-8")
    (extern_rules / "norms_firma.yaml").write_text(
        "obsolete:\n"
        "  - {pattern: 'WN\\\\s*4711', message: 'Werksnorm WN 4711 zurückgezogen'}\n",
        encoding="utf-8")
    m = reload_materials()
    try:
        assert any(x.name == "Hauswerkstoff X1" for x in m.MATERIALS)
        assert any("WN 4711" in msg for _, msg in m.OBSOLETE_NORMS)
    finally:
        os.environ.pop("DRAWING_CHECKER_RULES", None)
        reload_materials()


def test_external_profile_override(extern_rules):
    (extern_rules / "profiles_firma.yaml").write_text(
        "profiles:\n"
        "  default:\n"
        "    rules:\n"
        "      LANG.GERMAN: {enabled: true, severity: blocker}\n"
        "  sonderteile:\n"
        "    inherit: default\n", encoding="utf-8")
    from drawing_checker.kern import Severity

    prof = base.load_profile("default")
    assert prof.severity("LANG.GERMAN") == Severity.BLOCKER
    assert "sonderteile" in base.load_profiles_data()


def test_validator_reports_broken_entries(extern_rules):
    (extern_rules / "materials_kaputt.yaml").write_text(
        "materials:\n"
        "  - {name: Kaputt1, patterns: ['('], category: baustahl}\n"
        "  - {name: Kaputt2, patterns: ['ok'], category: gibtesnicht}\n"
        "  - {patterns: ['ok2'], category: baustahl}\n", encoding="utf-8")
    (extern_rules / "norms_kaputt.yaml").write_text(
        "obsolete:\n  - {pattern: '[', message: 'x'}\n", encoding="utf-8")
    issues, _ = validate_rules()
    text = "\n".join(map(str, issues))
    assert "ungültiges Regex-Muster" in text
    assert "gibtesnicht" in text
    assert "Pflichtfeld 'name' fehlt" in text
    assert len([i for i in issues if "kaputt" in i.file]) >= 4


def test_broken_entries_do_not_crash_loading(extern_rules):
    (extern_rules / "materials_kaputt.yaml").write_text(
        "materials:\n  - {name: Kaputt, patterns: 12, category: baustahl}\n",
        encoding="utf-8")
    m = reload_materials()
    try:
        assert len(m.MATERIALS) >= 60  # mitgelieferte Pakete bleiben nutzbar
    finally:
        os.environ.pop("DRAWING_CHECKER_RULES", None)
        reload_materials()
