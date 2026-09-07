"""Regelwerk: Profile, Wissenspakete und die Prüfungen an der Zeichnung.

Der grösste Testblock, weil hier das Fachwissen sitzt. Zu jeder Regel
gehört mindestens ein Positiv- und ein Negativfall.
"""
from __future__ import annotations

# ======================================================================
# profiles
# ======================================================================
from drawing_checker.regeln import load_profile
from drawing_checker.kern import Severity


def test_default_profile():
    p = load_profile("default")
    assert p.enabled("GT.GENERAL_TOL")
    assert p.severity("GEO.MISMATCH") == Severity.BLOCKER
    assert p.step_tolerance["rel"] == 0.05


def test_guss_inherits_and_overrides():
    p = load_profile("guss")
    # geerbt
    assert p.enabled("LANG.GERMAN")
    assert p.severity("LANG.GERMAN") == Severity.ERROR
    # überschrieben
    assert p.step_tolerance["rel"] == 0.12
    assert p.severity("GEO.MISMATCH") == Severity.WARNING


def test_unknown_profile_falls_back_to_default():
    p = load_profile("gibt_es_nicht")
    assert p.name == "default"


def test_title_block_keywords_configured():
    p = load_profile("default")
    kws = p.rule_param("TB.MATERIAL", "keywords")
    assert "Werkstoff" in kws and "Material" in kws


# ======================================================================
# rule_catalog
# ======================================================================
# Der Regelkatalog muss vollständig bleiben.
#
# Neue Regeln ohne Eintrag in README.md fallen hier auf – damit die
# Dokumentation für den Fachbereich nicht hinter dem Code zurückbleibt.
import re
from pathlib import Path

from drawing_checker.regeln import load_profile, load_profiles_data

KATALOG = Path(__file__).resolve().parent.parent / "README.md"


def documented_codes() -> set[str]:
    text = KATALOG.read_text(encoding="utf-8")
    return set(re.findall(r"`([A-Z]+\.[A-Z_0-9]+)`", text))


def all_rule_codes() -> set[str]:
    codes: set[str] = set()
    for name in load_profiles_data():
        codes |= set(load_profile(name).rules)
    return codes


def test_every_rule_is_documented():
    missing = sorted(all_rule_codes() - documented_codes())
    assert not missing, f"nicht im Regelkatalog dokumentiert: {missing}"


def test_catalog_has_no_stale_entries():
    """Dokumentierte Codes müssen im Regelwerk existieren."""
    stale = sorted(documented_codes() - all_rule_codes())
    assert not stale, f"im Katalog, aber nicht im Regelwerk: {stale}"


def test_catalog_states_rule_count():
    count = len(load_profile("default").rules)
    assert str(count) in KATALOG.read_text(encoding="utf-8"), (
        f"Regelanzahl im Katalog aktualisieren: aktuell {count}")


# ======================================================================
# rules_maintenance
# ======================================================================
# Manuelle Pflege der Wissenspakete: externer regeln/-Ordner + Validierung.
import os

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


# ======================================================================
# language
# ======================================================================
from drawing_checker.pruef_zeichnung import classify_block


def test_pure_german():
    assert classify_block("Alle Kanten gebrochen und entgratet") == "de"
    assert classify_block("Nach dem Schweißen spannungsarm glühen") == "de"


def test_pure_english():
    assert classify_block("All edges broken and deburred") == "en"


def test_bilingual_is_mixed():
    assert classify_block("Maßstab / Scale") == "mixed"
    assert classify_block("Werkstoff / Material") == "mixed"
    assert classify_block("Kanten / Edges: ISO 13715 -0,3") == "mixed"
    assert classify_block(
        "Wärmebehandlung / Heat treatment: vergütet / quenched") == "mixed"


def test_neutral_content():
    assert classify_block("ISO 2768-mK") == "neutral"
    assert classify_block("Ra 3,2") == "neutral"
    assert classify_block("⌀40 H7") == "neutral"
    assert classify_block("42CrMo4 +QT") == "neutral"


# ======================================================================
# materials
# ======================================================================
# Tests für Werkstofferkennung und fachliche Widerspruchsprüfung.
#
# Die Prüf-PDFs werden zur Laufzeit aus Textzeilen gebaut (echte PDFs mit
# Textlayer), damit exakt derselbe Extraktionspfad wie in Produktion läuft.

import pymupdf

from drawing_checker.regeln import CheckContext, load_profile
from drawing_checker.pruef_werkstoff import ( find_materials, run_material_checks, )
from drawing_checker.kern import PackageContent, Severity
from drawing_checker.zeichnung import DrawingPdf
from conftest import FONT, codes, make_ctx







# ------------------------------------------------------------- Erkennung
def test_find_material_variants(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: 1.4305", "alternativ X5CrNi18-10"])
    names = [h.material.name for h in find_materials(ctx)]
    assert "1.4305 (X8CrNiS18-9)" in names
    assert "1.4301 (X5CrNi18-10)" in names


def test_material_missing(tmp_path):
    ctx = make_ctx(tmp_path, ["Maßstab 1:2", "Allgemeintoleranzen ISO 2768-mK"])
    c = codes(ctx, run_material_checks)
    assert "MAT.MISSING" in c
    assert c["MAT.MISSING"].severity == Severity.ERROR


def test_material_label_but_unknown(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: Unobtainium X99"])
    c = codes(ctx, run_material_checks)
    assert c["MAT.MISSING"].severity == Severity.WARNING


def test_material_present_no_finding(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: S355J2+N"])
    assert "MAT.MISSING" not in codes(ctx, run_material_checks)


# ---------------------------------------------------- Widerspruch Schweißen
def test_1_4305_with_weld_is_conflict(tmp_path):
    ctx = make_ctx(tmp_path, [
        "Werkstoff: 1.4305",
        "Schweißnaht a4 umlaufend, ISO 5817-C",
    ])
    c = codes(ctx, run_material_checks)
    assert "MAT.WELD_CONFLICT" in c
    assert c["MAT.WELD_CONFLICT"].severity == Severity.ERROR
    assert "1.4305" in c["MAT.WELD_CONFLICT"].text


def test_s355_with_weld_is_fine(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: S355J2", "a4 ISO 5817-B umlaufend"])
    assert "MAT.WELD_CONFLICT" not in codes(ctx, run_material_checks)


def test_42crmo4_weld_is_limited_warning(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: 42CrMo4 +QT", "geschweißt nach ISO 5817-B"])
    c = codes(ctx, run_material_checks)
    assert c["MAT.WELD_CONFLICT"].severity == Severity.WARNING


def test_gg25_weld_conflict(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff EN-GJL-250", "Naht a3 ringsum"])
    assert "MAT.WELD_CONFLICT" in codes(ctx, run_material_checks)


# ---------------------------------------------- Widerspruch Wärmebehandlung
def test_s235_hardened_is_conflict(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: S235JR", "Oberfläche gehärtet 55 HRC"])
    assert "MAT.HT_CONFLICT" in codes(ctx, run_material_checks)


def test_c45_hardened_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: C45E", "gehärtet und angelassen"])
    assert "MAT.HT_CONFLICT" not in codes(ctx, run_material_checks)


def test_16mncr5_case_hardened_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff 16MnCr5", "einsatzgehärtet Eht 0,8"])
    assert "MAT.HT_CONFLICT" not in codes(ctx, run_material_checks)


def test_pa6_heat_treatment_nonsense(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: PA6 GF30", "vergütet"])
    assert "MAT.HT_CONFLICT" in codes(ctx, run_material_checks)


# --------------------------------------------------- Widerspruch Beschichtung
def test_stainless_galvanized_conflict(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: 1.4301", "feuerverzinkt nach ISO 1461"])
    assert "MAT.COATING_CONFLICT" in codes(ctx, run_material_checks)


def test_steel_anodized_conflict(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: S355J2", "schwarz eloxiert"])
    assert "MAT.COATING_CONFLICT" in codes(ctx, run_material_checks)


def test_alu_anodized_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff EN AW-6082", "natur eloxiert 15 µm"])
    assert "MAT.COATING_CONFLICT" not in codes(ctx, run_material_checks)


# --------------------------------------------------------- Norm vs. Werkstoff
def test_alu_with_iso5817_mismatch(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff EN AW-5754", "Schweißnahtgüte ISO 5817-C"])
    assert "NORM.MATERIAL_MISMATCH" in codes(ctx, run_material_checks)


def test_steel_with_iso10042_mismatch(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Nahtgüte ISO 10042-B"])
    assert "NORM.MATERIAL_MISMATCH" in codes(ctx, run_material_checks)


# -------------------------------------------------------------- Guss-Kontext
def test_cast_context_without_cast_material(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: C45", "Gussteil nach ISO 8062-3 DCTG12"])
    assert "MAT.CAST_CONFLICT" in codes(ctx, run_material_checks)


def test_cast_context_with_gjs_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff EN-GJS-400-15", "Gusstoleranzen ISO 8062"])
    assert "MAT.CAST_CONFLICT" not in codes(ctx, run_material_checks)


# ---------------------------------------------------------- Veraltete Normen
def test_obsolete_norms_flagged(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff S235JR",
                              "Oberflächen nach ISO 1302",
                              "Allgemeintoleranzen DIN 7168-m"])
    run_material_checks(ctx)
    msgs = [f.text for f in ctx.findings if f.code == "NORM.OBSOLETE"]
    assert any("21920" in m for m in msgs)
    assert any("7168" in m for m in msgs)


def test_current_norms_not_flagged(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff S235JR", "ISO 21920, ISO 13715,",
                              "ISO 2768-mK"])
    assert "NORM.OBSOLETE" not in codes(ctx, run_material_checks)


# ======================================================================
# process_rules
# ======================================================================
# Verfahrensspezifische Vollständigkeit: Schweißen, Guss, Blech.


from drawing_checker.pruef_werkstoff import run_process_checks
from drawing_checker.zeichnung import extract_dimensions
from conftest import FONT, make_ctx





def codes_verfahren(ctx) -> dict:
    run_process_checks(ctx, extract_dimensions(ctx.pdf))
    return {f.code: f for f in ctx.findings}


# ------------------------------------------------------------- Schweißen
def test_weld_without_size_is_error(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S355J2",
                                  "Kehlnaht umlaufend, ISO 5817-C"]))
    assert c["WELD.NO_SIZE"].severity == Severity.ERROR


def test_weld_with_a_size_is_fine(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S355J2",
                                  "Kehlnaht a4 umlaufend, ISO 5817-C"]))
    assert "WELD.NO_SIZE" not in c


def test_weld_with_z_size_is_fine(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S355J2",
                                  "Kehlnaht z6 umlaufend"]))
    assert "WELD.NO_SIZE" not in c


def test_mixed_a_and_z_sizes_warn(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S355J2",
                                  "Naht 1: a4 umlaufend",
                                  "Naht 2: z6 beidseitig"]))
    assert c["WELD.AZ_MIXED"].severity == Severity.WARNING
    assert "29" in c["WELD.AZ_MIXED"].detail


def test_butt_weld_without_preparation_warns(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S355J2",
                                  "V-Naht durchgeschweißt a6, ISO 5817-B"]))
    assert c["WELD.NO_PREP"].severity == Severity.WARNING


def test_butt_weld_with_preparation_is_fine(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, [
        "Werkstoff S355J2", "V-Naht a6, Nahtvorbereitung nach ISO 9692-1",
        "Öffnungswinkel 60°, Wurzelspalt 2 mm"]))
    assert "WELD.NO_PREP" not in c


def test_no_weld_context_no_findings(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff C45", "gedrehtes Teil"]))
    assert not [k for k in c if k.startswith("WELD.")]


# ------------------------------------------------------------------ Guss
def test_casting_without_draft_warns(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff EN-GJS-400-15",
                                  "Gussteil nach ISO 8062-3 DCTG12"]))
    assert c["CAST.NO_DRAFT"].severity == Severity.WARNING


def test_casting_with_draft_is_fine(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff EN-GJS-400-15", "Gussteil",
                                  "Formschrägen 2° wenn nicht anders angegeben",
                                  "Bearbeitungszugabe 3 mm"]))
    assert "CAST.NO_DRAFT" not in c
    assert "CAST.NO_RMA" not in c


def test_machined_casting_without_rma_warns(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff EN-GJL-250", "Gussteil",
                                  "Formschrägen 2°",
                                  "Passflächen bearbeitet, Ra 3,2"]))
    assert c["CAST.NO_RMA"].severity == Severity.WARNING


def test_unmachined_casting_needs_no_rma(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff EN-GJL-250",
                                  "Gussteil roh, Formschrägen 3°"]))
    assert "CAST.NO_RMA" not in c


# ----------------------------------------------------------------- Blech
def test_sheet_without_thickness_is_error(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S235JR",
                                  "Blech lasergeschnitten, abgekantet"]))
    assert c["SHEET.NO_THICK"].severity == Severity.ERROR


def test_sheet_with_thickness_is_fine(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S235JR",
                                  "Blechdicke 3 mm, abgekantet",
                                  "Biegeradius innen R3"]))
    assert "SHEET.NO_THICK" not in c
    assert "SHEET.NO_RADIUS" not in c


def test_bending_without_radius_warns(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S235JR", "Blechdicke 2 mm",
                                  "abgekantet 90°"]))
    assert c["SHEET.NO_RADIUS"].severity == Severity.WARNING


def test_flat_sheet_needs_no_radius(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S235JR", "Blechdicke 2 mm",
                                  "Blech lasergeschnitten, eben"]))
    assert "SHEET.NO_RADIUS" not in c


def test_turned_part_no_process_findings(tmp_path):
    """Ein Drehteil darf keine Schweiß-, Guss- oder Blechregel auslösen."""
    c = codes_verfahren(make_ctx(tmp_path, [
        "Werkstoff 42CrMo4 +QT", "Antriebswelle, gedreht und geschliffen",
        "⌀40 k6, Ra 0,8, Allgemeintoleranzen ISO 2768-fH"]))
    assert not c, f"unerwartete Findings: {list(c)}"


# ------------------------------------------------------ Wärmebehandlung
def test_heat_treatment_without_hardness_warns(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff 42CrMo4", "vergütet"]))
    assert c["HT.NO_HARDNESS"].severity == Severity.WARNING


def test_heat_treatment_with_hardness_is_fine(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff 42CrMo4",
                                  "vergütet auf 30-34 HRC"]))
    assert "HT.NO_HARDNESS" not in c


def test_case_hardening_without_depth_warns(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff 16MnCr5",
                                  "einsatzgehärtet 60 HRC"]))
    assert c["HT.NO_DEPTH"].severity == Severity.WARNING


def test_case_hardening_with_depth_is_fine(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff 16MnCr5",
                                  "einsatzgehärtet 60 HRC, Eht 0,8 mm"]))
    assert "HT.NO_DEPTH" not in c


def test_nitriding_with_nhd_is_fine(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff 31CrMoV9",
                                  "nitriert 700 HV1, NHD 0,4 mm"]))
    assert "HT.NO_DEPTH" not in c


def test_hardness_above_material_limit_is_error(tmp_path):
    """C45 erreicht rund 58 HRC – 64 HRC sind nicht darstellbar."""
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff C45",
                                  "randschichtgehärtet 64 HRC, Rht 1,5 mm"]))
    assert c["HT.HARDNESS_LIMIT"].severity == Severity.ERROR
    assert "C45" in c["HT.HARDNESS_LIMIT"].text


def test_hardness_within_limit_is_fine(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff 100Cr6",
                                  "durchgehärtet 62 HRC"]))
    assert "HT.HARDNESS_LIMIT" not in c


def test_hardness_limit_needs_known_material(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff Sonderlegierung XY",
                                  "gehärtet 70 HRC"]))
    assert "HT.HARDNESS_LIMIT" not in c


def test_normed_delivery_state_needs_no_hardness(tmp_path):
    """Bei +QT/+N ist der Zustand normativ definiert (EN 10083)."""
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff 42CrMo4 +QT",
                                  "vergütet / quenched and tempered"]))
    assert "HT.NO_HARDNESS" not in c


def test_strength_specification_replaces_hardness(tmp_path):
    c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff C45", "vergütet",
                                  "Rm ≥ 700 N/mm²"]))
    assert "HT.NO_HARDNESS" not in c


# ======================================================================
# new_rules
# ======================================================================
# Tests der Praxisregeln: Eloxal-Legierung, Schweißbolzen/Verzinkung,
# GD&T-Widersprüche, Positionsballone.


from drawing_checker.pruef_zeichnung import run_drawing_checks







# ------------------------------------------------ Eloxal-Legierungswahl
def test_cast_alloy_anodized_is_error(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff: AlSi10Mg", "schwarz eloxiert"]), run_drawing_checks)
    assert c["MAT.ANODIZE_ALLOY"].severity == Severity.ERROR


def test_alcu_alloy_anodized_is_error(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff EN AW-2007", "eloxiert natur"]), run_drawing_checks)
    assert "MAT.ANODIZE_ALLOY" in c


def test_7075_anodized_is_warning(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff EN AW-7075", "anodized type II"]), run_drawing_checks)
    assert c["MAT.ANODIZE_ALLOY"].severity == Severity.WARNING


def test_6082_anodized_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff EN AW-6082", "eloxiert 15 µm"]), run_drawing_checks)
    assert "MAT.ANODIZE_ALLOY" not in c


# ---------------------------------------- Schweißbolzen auf Verzinkung
def test_stud_weld_on_galvanized_is_error(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff: S235JR",
        "Blech feuerverzinkt nach ISO 1461",
        "4x Schweißbolzen M8 ISO 13918",
    ]), run_drawing_checks)
    assert c["PROC.STUD_ON_ZINC"].severity == Severity.ERROR


def test_weld_and_zinc_without_sequence_is_warning(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff: S355J2", "Naht a4 umlaufend, ISO 5817-C",
        "Baugruppe feuerverzinkt",
    ]), run_drawing_checks)
    assert c["PROC.WELD_ZINC_ORDER"].severity == Severity.WARNING


def test_weld_and_zinc_with_sequence_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff: S355J2", "Naht a4 umlaufend, ISO 5817-C",
        "Nach dem Schweißen komplett feuerverzinken (ISO 1461)",
    ]), run_drawing_checks)
    assert "PROC.WELD_ZINC_ORDER" not in c
    assert "PROC.STUD_ON_ZINC" not in c


# ---------------------------------------------------- GD&T-Widersprüche
def test_form_tolerance_with_datum_is_error(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff C45", "⏥ 0,1 A"]), run_drawing_checks)
    assert c["GPS.FORM_WITH_DATUM"].severity == Severity.ERROR


def test_form_tolerance_without_datum_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff C45", "⏥ 0,1", "○ 0,05"]), run_drawing_checks)
    assert "GPS.FORM_WITH_DATUM" not in c


def test_deprecated_concentricity_symbol_warns(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff C45", "◎ ⌀0,2 A", "Bezug A"]), run_drawing_checks)
    assert c["GPS.DEPRECATED_SYMBOL"].severity == Severity.WARNING


# ------------------------------------------------------ Positionsballone
BOM = [
    (600, "Stückliste"),
    (600, "Pos. Menge Benennung"),
    (600, "1 2 Grundplatte"),
    (600, "2 1 Rippe"),
]


def test_bom_without_balloons_warns(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff S235JR"] + BOM), run_drawing_checks)
    assert c["DOC.BALLOONS"].severity == Severity.WARNING


def test_bom_with_balloons_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff S235JR",
        (100, "1"), (150, "2"),   # Ballon-Nummern an den Teilen
    ] + BOM), run_drawing_checks)
    assert "DOC.BALLOONS" not in c


def test_no_bom_no_balloon_check(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff S235JR", "Einzelteil"]), run_drawing_checks)
    assert "DOC.BALLOONS" not in c


# ------------------------------------ Beschichtung vs. Passung/Gewinde
def test_zinc_with_fit_warns(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff S355J2", "Bohrung ⌀22 H7", "feuerverzinkt ISO 1461"]), run_drawing_checks)
    assert c["COAT.FIT"].severity == Severity.WARNING


def test_zinc_with_fit_and_note_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff S355J2", "Bohrung ⌀22 H7",
        "feuerverzinkt ISO 1461, Passung H7 nach dem Verzinken nachreiben"]), run_drawing_checks)
    assert "COAT.FIT" not in c


def test_anodize_with_thread_warns(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff EN AW-6082", "Gewinde M8", "schwarz eloxiert"]), run_drawing_checks)
    assert "COAT.FIT" in c


def test_zinc_without_fit_no_warning(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff S235JR", "feuerverzinkt"]), run_drawing_checks)
    assert "COAT.FIT" not in c


# ------------------------------------------------ Brünieren auf Nichtstahl
def test_blackening_on_stainless_conflict(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff 1.4301", "brüniert"]), run_drawing_checks)
    assert "MAT.COATING_CONFLICT" in c


def test_blackening_on_steel_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff C45", "brüniert"]), run_drawing_checks)
    assert "MAT.COATING_CONFLICT" not in c


# ------------------------------------------------------ Mischverbindungen
def test_alu_plus_steel_welded_is_error(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Pos 1: S235JR", "Pos 2: EN AW-5754", "geschweißt nach ISO 5817-C"]), run_drawing_checks)
    assert c["WELD.MIXED"].severity == Severity.ERROR


def test_stainless_plus_steel_needs_filler(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Pos 1: S355J2", "Pos 2: 1.4301", "Naht a3 umlaufend"]), run_drawing_checks)
    assert c["WELD.MIXED_FILLER"].severity == Severity.WARNING


def test_stainless_plus_steel_with_309_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Pos 1: S355J2", "Pos 2: 1.4301",
        "Naht a3 umlaufend, Zusatzwerkstoff 309L"]), run_drawing_checks)
    assert "WELD.MIXED_FILLER" not in c


# --------------------------------------- Schweißteil nur mit ISO 2768
def test_weld_with_only_2768_warns(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff S355J2", "geschweißt ISO 5817-C",
        "Allgemeintoleranzen ISO 2768-mK"]), run_drawing_checks)
    assert c["NORM.WELD_GENTOL"].severity == Severity.WARNING


def test_weld_with_13920_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff S355J2", "geschweißt ISO 5817-C",
        "Allgemeintoleranzen ISO 2768-mK und ISO 13920-BF"]), run_drawing_checks)
    assert "NORM.WELD_GENTOL" not in c


# -------------------------------------------- Gewinde mit Passungsklasse
def test_thread_with_fit_class_is_error(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff C45", "Gewinde M12 H7"]), run_drawing_checks)
    assert c["THRD.FIT_CLASS"].severity == Severity.ERROR


def test_thread_with_correct_class_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff C45", "Gewinde M12 - 6H"]), run_drawing_checks)
    assert "THRD.FIT_CLASS" not in c


# ======================================================================
# dimensions
# ======================================================================
from drawing_checker.kern import BBox
from drawing_checker.zeichnung import ( DimKind, _parse_word, estimate_envelope, extract_dimensions, )
from drawing_checker.zeichnung import Word


def w(text: str) -> Word:
    return Word(text, BBox(0, 0, 10, 10), 0)


def parse(text: str, prev: str = ""):
    return _parse_word(w(text), prev)


def kinds(text: str, prev: str = ""):
    return [(d.kind, d.value) for d in parse(text, prev)]


def test_diameter_variants():
    assert kinds("⌀40") == [(DimKind.DIAMETER, 40.0)]
    assert kinds("Ø22 H11") == [(DimKind.DIAMETER, 22.0)]
    assert kinds("4×⌀18")[0] == (DimKind.DIAMETER, 18.0)


def test_linear_with_tolerances_and_fits():
    assert kinds("420") == [(DimKind.LINEAR, 420.0)]
    assert kinds("120,5") == [(DimKind.LINEAR, 120.5)]
    assert kinds("60±0,2")[0][1] == 60.0
    assert kinds("40H7") == [(DimKind.LINEAR, 40.0)]


def test_radius_and_thread():
    assert kinds("R5") == [(DimKind.RADIUS, 5.0)]
    assert kinds("M12x1,5") == [(DimKind.THREAD, 12.0)]


def test_exclusions():
    assert parse("2768", prev="iso") == []          # Normbezug
    assert parse("1:2") == []                        # Maßstab
    assert parse("10473215") == []                   # Materialnummer
    assert parse("2025") == []                       # Jahr
    assert parse("45°") == []                        # Winkel
    assert parse("12,5kg") == []                     # Gewicht
    assert parse("1/1") == []                        # Blattangabe


def test_envelope_top_values():
    dims = [d for t in ("420", "⌀70", "120", "90", "80", "70", "60", "R3")
            for d in parse(t)]
    env = estimate_envelope(dims)
    assert env[0] == 420.0
    assert 3.0 not in env  # Radius zählt nicht als Hüllmaß


def test_extract_from_real_mock(mock_dir):
    from drawing_checker.zeichnung import DrawingPdf

    with DrawingPdf(mock_dir / "_arbeit" / "Z_10473217.pdf") as pdf:
        dims = extract_dimensions(pdf)
    values = {d.value for d in dims}
    assert 420.0 in values          # Gesamtlänge
    assert 55.0 in values           # ⌀55
    assert 2768.0 not in values     # ISO 2768 nicht als Maß


# ======================================================================
# fcf
# ======================================================================
# Toleranzrahmen-Erkennung (Feature Control Frames) als Vektorgrafik.
#
# Nutzt die echten Kalibrierzeichnungen aus mockdata/echt_quellen – nur dort
# liegen Toleranzrahmen so vor wie in der Praxis (Grafik statt Textsymbol).


from drawing_checker.pruef_bemassung import ( check_diameter_zone_needs_datum, check_gdt_readability, )
from drawing_checker.kern import BBox, PackageContent, Severity
from drawing_checker.zeichnung import FeatureFrame, find_feature_frames
from conftest import ECHT



pytestmark = pytest.mark.skipif(
    not (ECHT / "lensmount.pdf").exists(),
    reason="Kalibrierzeichnungen nicht vorhanden")


def test_frames_found_on_real_drawing():
    with DrawingPdf(ECHT / "lensmount.pdf") as pdf:
        frames = find_feature_frames(pdf)
    assert len(frames) >= 4
    assert all(f.value is not None for f in frames)


def test_datums_read_from_graphic_frame():
    with DrawingPdf(ECHT / "supportBracket.pdf") as pdf:
        frames = find_feature_frames(pdf)
    with_datums = [f for f in frames if f.has_datums]
    assert with_datums, "kein Rahmen mit Bezügen erkannt"
    assert with_datums[0].datums == ["A", "B", "C"]


def test_frames_are_deduplicated():
    with DrawingPdf(ECHT / "copperThermalMass.pdf") as pdf:
        frames = find_feature_frames(pdf)
    seen = {(f.page, round(f.bbox.x0), round(f.bbox.y0)) for f in frames}
    assert len(seen) == len(frames)


def test_drawing_without_gdt_has_no_frames():
    with DrawingPdf(ECHT / "thermalStrap.pdf") as pdf:
        assert find_feature_frames(pdf) == []


def _ctx(pdf_path: Path) -> CheckContext:
    return CheckContext("x", DrawingPdf(pdf_path), PackageContent(),
                        load_profile("default"))


def test_graphic_gdt_hint_is_info():
    ctx = _ctx(ECHT / "lensmount.pdf")
    check_gdt_readability(ctx)
    assert ctx.findings[0].code == "DOC.GDT_GRAPHIC"
    assert ctx.findings[0].severity == Severity.INFO


def test_no_hint_without_frames():
    ctx = _ctx(ECHT / "thermalStrap.pdf")
    check_gdt_readability(ctx)
    assert not ctx.findings


def test_diameter_zone_without_datum_is_error():
    ctx = _ctx(ECHT / "thermalStrap.pdf")
    ctx._frames = [FeatureFrame(bbox=BBox(0, 0, 50, 10), page=0,
                                texts=["⌀0,2"], value=0.2,
                                diameter_zone=True, datums=[])]
    check_diameter_zone_needs_datum(ctx)
    assert ctx.findings[0].code == "GPS.ZONE_NO_DATUM"
    assert ctx.findings[0].severity == Severity.ERROR


def test_diameter_zone_with_datum_is_fine():
    ctx = _ctx(ECHT / "thermalStrap.pdf")
    ctx._frames = [FeatureFrame(bbox=BBox(0, 0, 50, 10), page=0,
                                texts=["⌀0,2", "A"], value=0.2,
                                diameter_zone=True, datums=["A"])]
    check_diameter_zone_needs_datum(ctx)
    assert not ctx.findings


def test_plain_zone_without_datum_is_fine():
    """Ohne ⌀ kann es eine Formtoleranz sein – die braucht keinen Bezug."""
    ctx = _ctx(ECHT / "thermalStrap.pdf")
    ctx._frames = [FeatureFrame(bbox=BBox(0, 0, 50, 10), page=0,
                                texts=["0,05"], value=0.05,
                                diameter_zone=False, datums=[])]
    check_diameter_zone_needs_datum(ctx)
    assert not ctx.findings


# ======================================================================
# gps_dim_rules
# ======================================================================
# GPS-Tiefenprüfung, Bemaßungs- und Fertigungsregeln.
#
# Der Helfer platziert Texte an exakten Koordinaten, weil die Maßketten-
# Erkennung bewusst die räumliche Anordnung auswertet.


from drawing_checker.pruef_bemassung import run_dimension_checks
from drawing_checker.pruef_bemassung import run_gps_checks





class _FakeBlock:
    """Textblock-Stub mit Dummy-Position."""

    def __init__(self, text, i=0):
        from drawing_checker.kern import BBox
        self.text = text
        self.bbox = BBox(10, 10 + i * 20, 200, 25 + i * 20)
        self.page = 0


class _FakePdf:
    """PDF-Stub für symbolbasierte Tests.

    DejaVu (die Testschrift) kann ⌖/Ⓜ/Ⓔ nicht darstellen; echte CAD-PDFs
    schon. Der Stub liefert den Text direkt, damit die Symbolregeln
    unabhängig von der Schriftabdeckung geprüft werden können.
    """

    def __init__(self, lines):
        self._blocks = [_FakeBlock(t, i) for i, t in enumerate(lines)]

    def blocks(self):
        return self._blocks

    def full_text(self):
        return "\n".join(b.text for b in self._blocks)

    def words(self):
        from drawing_checker.kern import BBox
        from drawing_checker.zeichnung import Word
        out = []
        for b in self._blocks:
            for i, t in enumerate(b.text.split()):
                out.append(Word(t, BBox(b.bbox.x0 + i * 20, b.bbox.y0,
                                        b.bbox.x0 + i * 20 + 15, b.bbox.y1),
                                0))
        return out


def sym_ctx(lines, profile="default") -> CheckContext:
    return CheckContext("123", _FakePdf(lines), PackageContent(),
                        load_profile(profile))


def run_all(ctx) -> dict:
    dims = extract_dimensions(ctx.pdf)
    run_gps_checks(ctx, dims)
    run_dimension_checks(ctx, dims)
    return {f.code: f for f in ctx.findings}


# =========================================================== GPS-Regeln
def test_fit_without_envelope_warns():
    """Klassiker: ⌀20 H7 ohne Ⓔ – Form bleibt nach ISO 8015 unbegrenzt."""
    c = run_all(sym_ctx(["Werkstoff C45", "Lagersitz ⌀20 H7",
                         "Tolerierung ISO 8015"]))
    assert c["GPS.ENVELOPE"].severity == Severity.WARNING
    assert "H7" in c["GPS.ENVELOPE"].text


def test_fit_with_envelope_symbol_is_fine():
    c = run_all(sym_ctx(["Werkstoff C45", "⌀20 H7 Ⓔ"]))
    assert "GPS.ENVELOPE" not in c


def test_fit_with_form_tolerance_is_fine():
    c = run_all(sym_ctx(["Werkstoff C45", "⌀20 H7", "⌭ 0,01"]))
    assert "GPS.ENVELOPE" not in c


def test_coarse_fit_not_flagged():
    """Grobe Passungen (IT ≥ 9) sind unkritisch."""
    c = run_all(sym_ctx(["Werkstoff C45", "⌀22 H11"]))
    assert "GPS.ENVELOPE" not in c


def test_undefined_datum_is_error():
    c = run_all(sym_ctx(["Werkstoff C45", "⌖ ⌀0,2 X"]))
    assert c["GPS.DATUM_UNDEFINED"].severity == Severity.ERROR
    assert "X" in c["GPS.DATUM_UNDEFINED"].text


def test_defined_datum_is_fine():
    c = run_all(sym_ctx(["Werkstoff C45", "⌖ ⌀0,2 A",
                         "Bezug A = Auflagefläche"]))
    assert "GPS.DATUM_UNDEFINED" not in c


def test_position_without_ted_warns():
    c = run_all(sym_ctx(["Werkstoff C45", "⌖ ⌀0,2 A",
                         "Bezug A", "Abstand 50±0,1"]))
    assert c["GPS.POSITION_NO_TED"].severity == Severity.WARNING


def test_position_with_ted_is_fine():
    c = run_all(sym_ctx(["Werkstoff C45", "⌖ ⌀0,2 A",
                         "Bezug A", "[50]", "[30]"]))
    assert "GPS.POSITION_NO_TED" not in c


def test_modifier_on_form_tolerance_is_error():
    c = run_all(sym_ctx(["Werkstoff C45", "⏥ 0,05 Ⓜ"]))
    assert c["GPS.MOD_ON_FORM"].severity == Severity.ERROR


# ====================================================== Maßketten-Check
def test_closed_chain_detected(tmp_path):
    """Echte horizontale Kette: 20+30+50 = 100, Teil und Summe toleriert."""
    items = [
        (40, 300, "20±0,1"), (140, 300, "30±0,1"), (240, 300, "50±0,1"),
        (140, 340, "100±0,1"),
        (40, 60, "Werkstoff C45"),
    ]
    c = run_all(make_ctx(tmp_path, items))
    assert c["DIM.CHAIN"].severity == Severity.WARNING
    assert "Maßkette" in c["DIM.CHAIN"].text


def test_open_chain_is_fine(tmp_path):
    """Nur das Gesamtmaß toleriert = korrekte offene Kette."""
    items = [
        (40, 300, "20"), (140, 300, "30"), (240, 300, "50"),
        (140, 340, "100±0,1"),
        (40, 60, "Werkstoff C45"),
    ]
    c = run_all(make_ctx(tmp_path, items))
    assert "DIM.CHAIN" not in c


def test_scattered_dimensions_no_false_chain(tmp_path):
    """Zufällig passende Summen ohne gemeinsame Maßlinie -> kein Finding."""
    items = [
        (40, 100, "20±0,1"), (400, 250, "30±0,1"), (700, 480, "50±0,1"),
        (100, 520, "100±0,1"),
        (40, 60, "Werkstoff C45"),
    ]
    c = run_all(make_ctx(tmp_path, items))
    assert "DIM.CHAIN" not in c


# ================================================ Fertigungsgerechtigkeit
def test_tight_tolerance_flagged(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "Lagersitz ⌀30 h4",
                                    "Länge 80±0,003"]))
    assert c["MFG.TIGHT_TOL"].severity == Severity.WARNING


def test_normal_tolerance_not_flagged(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "⌀30 h9", "80±0,2"]))
    assert "MFG.TIGHT_TOL" not in c


def test_deep_hole_flagged(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "⌀8 ↧80"]))
    assert c["MFG.DEEP_HOLE"].severity == Severity.WARNING
    assert "10.0:1" in c["MFG.DEEP_HOLE"].text


def test_shallow_hole_not_flagged(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "⌀20 ↧40"]))
    assert "MFG.DEEP_HOLE" not in c


def test_sharp_corner_flagged(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "Innenecken R0"]))
    assert c["MFG.SHARP_CORNER"].severity == Severity.WARNING


def test_normal_radius_not_flagged(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "Innenecken R3"]))
    assert "MFG.SHARP_CORNER" not in c


# ============================================== Oberflächen-Plausibilität
def test_fine_ra_on_cast_surface_is_error(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff EN-GJL-250",
                                    "Gussteil, Oberfläche Ra 0,8"]))
    assert c["SURF.UNREALISTIC"].severity == Severity.ERROR


def test_fine_ra_with_grinding_is_fine(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff 42CrMo4",
                                    "Lagersitze geschliffen, Ra 0,2"]))
    assert "SURF.UNREALISTIC" not in c


def test_very_fine_ra_without_process_warns(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff 42CrMo4", "Ra 0,1"]))
    assert c["SURF.UNREALISTIC"].severity == Severity.WARNING


def test_normal_ra_is_fine(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff 42CrMo4", "Ra 3,2"]))
    assert "SURF.UNREALISTIC" not in c


# ================================================== Regressionsschutz
def test_clean_drawing_triggers_no_new_rules(tmp_path):
    """Eine saubere Zeichnung darf keine der neuen Regeln auslösen."""
    c = run_all(make_ctx(tmp_path, [
        "Werkstoff 42CrMo4 +QT",
        "Allgemeintoleranzen ISO 2768-fH, Tolerierung ISO 8015",
        "⌀40 h6 (E), ⌀55 h6 (E)",
        "Oberfläche Ra 1,6, Lagersitze geschliffen Ra 0,8",
        "Kanten ISO 13715, Innenradien R3",
    ]))
    new_codes = {k for k in c
                 if k.startswith(("GPS.", "DIM.", "MFG.", "SURF.UNREAL"))}
    assert not new_codes, f"unerwartete Findings: {new_codes}"


# ======================================================================
# scale
# ======================================================================
# Maßstabsextraktion und maßstabsbasierte Prüfungen.


from drawing_checker.pruef_zeichnung import ( check_scale_consistency, check_view_vs_model, )
from drawing_checker.pruef_geometrie import StepGeometry
from drawing_checker.zeichnung import DimKind, DimValue
from drawing_checker.zeichnung import extract_scale, mm_per_point
from conftest import ECHT, FONT





def make_pdf(tmp_path: Path, lines) -> DrawingPdf:
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    kwargs = {}
    if Path(FONT).exists():
        page.insert_font(fontname="T", fontfile=FONT)
        kwargs["fontname"] = "T"
    for i, line in enumerate(
            list(lines)
            + ["Interne Testzeichnung – Blatt 1 von 1, Ausgabestand 2026"]):
        page.insert_text((40, 60 + i * 30), line, fontsize=10, **kwargs)
    path = tmp_path / "t.pdf"
    doc.save(path)
    doc.close()
    return DrawingPdf(path)


def ctx_for(tmp_path, lines, profile="default") -> CheckContext:
    return CheckContext("123", make_pdf(tmp_path, lines), PackageContent(),
                        load_profile(profile))


# ------------------------------------------------------ Maßstabsextraktion
@pytest.mark.parametrize("text,expected", [
    ("Maßstab 1:2", 2.0),
    ("Maßstab / Scale 1:2,5", 2.5),
    ("SCALE: 2:1", 0.5),
    ("Maßstab 1:1", 1.0),
    ("Scale 1:10", 10.0),
])
def test_labelled_scales(tmp_path, text, expected):
    with make_pdf(tmp_path, [text]) as pdf:
        assert extract_scale(pdf) == pytest.approx(expected)


def test_unlabelled_ratio_is_ignored(tmp_path):
    """Blatt-/Zeitangaben dürfen nicht als Maßstab gelesen werden."""
    with make_pdf(tmp_path, ["Blatt 1/1", "Sheet 1:1 of 3", "08:30"]) as pdf:
        assert extract_scale(pdf) is None


def test_unusual_ratio_is_rejected(tmp_path):
    with make_pdf(tmp_path, ["Maßstab 1:3,7"]) as pdf:
        assert extract_scale(pdf) is None


def test_mm_per_point():
    assert mm_per_point(1.0) == pytest.approx(25.4 / 72)
    assert mm_per_point(2.0) == pytest.approx(2 * 25.4 / 72)


def test_scale_from_real_drawings():
    with DrawingPdf(ECHT / "lensmount.pdf") as pdf:
        assert extract_scale(pdf) == 1.0
    with DrawingPdf(ECHT / "CassegrainBase.pdf") as pdf:
        assert extract_scale(pdf) == 0.5


# ------------------------------------------- Messung und Bewertung
def test_measurement_reported_even_when_rule_disabled(mock_dir):
    """Die gemessene Ansichtsgröße gehört auch ohne Bewertung in die Excel."""
    with DrawingPdf(mock_dir / "_arbeit" / "Z_10473217.pdf") as pdf:
        ctx = CheckContext("10473217", pdf, PackageContent(),
                           load_profile("default"))
        summary = check_scale_consistency(ctx, [])
    assert "Ansicht gemessen" in summary
    assert "1:2" in summary
    assert not ctx.findings          # Regel ist im Auslieferzustand aus


def test_mock_drawings_are_exactly_to_scale(mock_dir):
    """Die Mockzeichnungen sind maßstabsgetreu – Messung trifft die Maße."""
    from drawing_checker.pruef_zeichnung import measure_largest_view

    with DrawingPdf(mock_dir / "_arbeit" / "Z_10473217.pdf") as pdf:
        ctx = CheckContext("x", pdf, PackageContent(), load_profile("default"))
        w, h, _view = measure_largest_view(ctx, extract_scale(pdf))
    assert w == pytest.approx(420, abs=6)     # Wellenlänge
    assert h == pytest.approx(70, abs=6)      # größter Durchmesser


def _enable(profile_name, *codes):
    prof = load_profile(profile_name)
    for c in codes:
        prof.rules.setdefault(c, {})["enabled"] = True
    return prof


def test_oversized_view_is_flagged_when_enabled(tmp_path):
    ctx = ctx_for(tmp_path, ["Maßstab 1:1", "Werkstoff C45"])
    ctx.profile = _enable("default", "SCALE.MISMATCH")
    # Ansicht künstlich groß: Stub über measure ersetzen
    import drawing_checker.pruef_zeichnung as sc

    class _V:
        bbox = (0, 0, 500, 200)
    orig = sc.measure_largest_view
    sc.measure_largest_view = lambda c, s: (200.0, 80.0, _V())
    try:
        check_scale_consistency(ctx, [DimValue(50, DimKind.LINEAR, "50",
                                               BBox(0, 0, 1, 1), 0)])
    finally:
        sc.measure_largest_view = orig
    assert ctx.findings[0].code == "SCALE.MISMATCH"
    assert ctx.findings[0].severity == Severity.WARNING


def test_undersized_view_is_never_flagged(tmp_path):
    """Zu klein gemessene Ansichten sind ein Erkennungsproblem, kein Fehler."""
    ctx = ctx_for(tmp_path, ["Maßstab 1:1", "Werkstoff C45"])
    ctx.profile = _enable("default", "SCALE.MISMATCH")
    import drawing_checker.pruef_zeichnung as sc

    class _V:
        bbox = (0, 0, 100, 50)
    orig = sc.measure_largest_view
    sc.measure_largest_view = lambda c, s: (30.0, 20.0, _V())
    try:
        check_scale_consistency(ctx, [DimValue(200, DimKind.LINEAR, "200",
                                               BBox(0, 0, 1, 1), 0)])
    finally:
        sc.measure_largest_view = orig
    assert not ctx.findings


def test_view_vs_model_needs_occ(tmp_path):
    ctx = ctx_for(tmp_path, ["Maßstab 1:1"])
    ctx.profile = _enable("default", "GEO.VIEW_SIZE")
    geo = StepGeometry(obb_dims=(50, 20, 10), backend="fallback")
    check_view_vs_model(ctx, geo, [])
    assert not ctx.findings


# ======================================================================
# beschaffung_und_masse
# ======================================================================
# Tests der Regeln aus Runde 3: Masse-Plausibilität, Dokumenten-Formalien,
# internationale Beschaffung, Bemaßungswidersprüche, Wasserstoffversprödung.
#
# Zu jeder Regel ein Positiv- und ein Negativfall (Konvention aus CLAUDE.md).


from drawing_checker.pruef_bemassung import ( check_roughness_vs_tolerance, check_tolerance_order, )
from drawing_checker.pruef_zeichnung import run_doc_checks
from drawing_checker.pruef_werkstoff import ( check_density_hint, check_mass_plausibility, )
from drawing_checker.pruef_werkstoff import check_hydrogen_embrittlement
from drawing_checker.pruef_werkstoff import run_purchasing_checks
from drawing_checker.zeichnung import ( DimKind, DimValue, extract_dimensions, )





def dims_of(ctx) -> list[DimValue]:
    return extract_dimensions(ctx.pdf, 6000)




# ------------------------------------------------------ Masse-Plausibilität
def _dim(value: float, kind: DimKind = DimKind.LINEAR, **kw) -> DimValue:
    return DimValue(value=value, kind=kind, raw=f"{value:g}",
                    bbox=BBox(0, 0, 10, 10), page=0, **kw)


def test_mass_impossible_is_error(tmp_path):
    """100 kg auf 100×80×20 mm Stahl (max. 1,3 kg) kann nicht stimmen."""
    ctx = make_ctx(tmp_path, ["Werkstoff: S235JR", "Gewicht: 100 kg"])
    check_mass_plausibility(ctx, [_dim(100), _dim(80), _dim(20)])
    assert "MASS.IMPOSSIBLE" in codes(ctx)
    assert ctx.findings[0].severity == Severity.ERROR


def test_mass_impossible_nennt_einheitenverdacht(tmp_path):
    """Faktor ≈ 1000 -> Hinweis auf g/kg-Verwechslung."""
    # 100x80x60 mm Stahl = 3,77 kg; angegeben ist das 1000-fache.
    ctx = make_ctx(tmp_path, ["Werkstoff: S235JR", "Gewicht: 3768 kg"])
    check_mass_plausibility(ctx, [_dim(100), _dim(80), _dim(60)])
    assert "g statt kg" in ctx.findings[0].detail


def test_mass_plausibel_meldet_nicht(tmp_path):
    """0,9 kg auf 100×80×20 Stahl (max. 1,26 kg) ist plausibel."""
    ctx = make_ctx(tmp_path, ["Werkstoff: S235JR", "Gewicht: 0,9 kg"])
    summary = check_mass_plausibility(ctx, [_dim(100), _dim(80), _dim(20)])
    assert not codes(ctx)
    assert "Füllgrad" in summary


def test_mass_ohne_werkstoff_nicht_pruefbar(tmp_path):
    ctx = make_ctx(tmp_path, ["Gewicht: 100 kg"])
    assert check_mass_plausibility(ctx, [_dim(100), _dim(80), _dim(20)]) == ""
    assert not codes(ctx)


def test_mass_too_light(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: S235JR", "Gewicht: 0,005 kg"])
    check_mass_plausibility(ctx, [_dim(200), _dim(200), _dim(50)])
    assert "MASS.TOO_LIGHT" in codes(ctx)


def test_density_hint_erkennt_falschen_werkstoff(tmp_path):
    """1 kg auf 128 cm³ = 7,8 g/cm³ – angegeben ist aber Aluminium."""
    ctx = make_ctx(tmp_path, ["Werkstoff: EN AW-6060", "Gewicht: 1,00 kg"])
    check_density_hint(ctx, model_volume_mm3=128000.0)
    assert "MASS.DENSITY_HINT" in codes(ctx)
    assert "g/cm³" in ctx.findings[0].text


def test_density_hint_schweigt_wenn_passend(tmp_path):
    """345 g auf 128 cm³ = 2,7 g/cm³ – passt zu Aluminium."""
    ctx = make_ctx(tmp_path, ["Werkstoff: EN AW-6060", "Gewicht: 0,345 kg"])
    check_density_hint(ctx, model_volume_mm3=128000.0)
    assert not codes(ctx)


def test_fertiggewicht_schlaegt_rohgewicht(tmp_path):
    from drawing_checker.zeichnung import extract_weight_kg

    ctx = make_ctx(tmp_path, ["Rohteilgewicht: 12,0 kg", "Gewicht: 7,5 kg"])
    assert extract_weight_kg(ctx.pdf) == 7.5


# ------------------------------------------------------ Dokument-Formalien
def test_sheet_count_erkennt_fehlende_blaetter(tmp_path):
    ctx = make_ctx(tmp_path, ["Blatt 1 von 3", "Werkstoff: S235JR"])
    run_doc_checks(ctx)
    assert "DOC.SHEET_COUNT" in codes(ctx)


def test_sheet_count_ok_bei_vollstaendigem_paket(tmp_path):
    ctx = make_ctx(tmp_path, ["Blatt 1 von 2"], pages=2)
    run_doc_checks(ctx)
    assert "DOC.SHEET_COUNT" not in codes(ctx)


def test_annotations_werden_gemeldet(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((40, 60), "Werkstoff: S235JR", fontsize=10)
    page.add_text_annot((100, 100), "bitte noch aendern")
    path = tmp_path / "markup.pdf"
    doc.save(path)
    doc.close()
    ctx = CheckContext("1", DrawingPdf(path), PackageContent(),
                       load_profile("default"))
    run_doc_checks(ctx)
    assert "DOC.ANNOTATIONS" in codes(ctx)


def test_sauberes_pdf_ohne_annotationsmeldung(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: S235JR"])
    run_doc_checks(ctx)
    assert "DOC.ANNOTATIONS" not in codes(ctx)


def test_datum_in_der_zukunft(tmp_path):
    ctx = make_ctx(tmp_path, ["Aenderung vom 01.01.2099", "Werkstoff: S235JR"])
    run_doc_checks(ctx)
    assert "DOC.DATE_FUTURE" in codes(ctx)


def test_gemischte_dezimaltrenner(tmp_path):
    ctx = make_ctx(tmp_path, ["12,5  30,2  8,75", "12.5  30.2  8.75"])
    run_doc_checks(ctx)
    assert "DOC.DECIMAL_MIXED" in codes(ctx)


def test_einheitlicher_dezimaltrenner_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["12,5  30,2  8,75  40,0"])
    run_doc_checks(ctx)
    assert "DOC.DECIMAL_MIXED" not in codes(ctx)


# ------------------------------------------------ Internationale Beschaffung
def test_vage_angabe_wird_gemeldet(tmp_path):
    ctx = make_ctx(tmp_path, ["Bohrung ca. 12 mm", "Oberflaeche nach Absprache"])
    run_purchasing_checks(ctx, [])
    assert "PUR.VAGUE_SPEC" in codes(ctx)


def test_praezise_angabe_ohne_meldung(tmp_path):
    ctx = make_ctx(tmp_path, ["Bohrung 12 H7", "Ra 1,6"])
    run_purchasing_checks(ctx, [])
    assert "PUR.VAGUE_SPEC" not in codes(ctx)


def test_hausnorm_wird_gemeldet(tmp_path):
    ctx = make_ctx(tmp_path, ["Oberflaeche nach WN 51204"])
    run_purchasing_checks(ctx, [])
    assert "PUR.INTERNAL_NORM" in codes(ctx)


def test_oeffentliche_norm_ohne_meldung(tmp_path):
    ctx = make_ctx(tmp_path, ["Oberflaeche nach EN ISO 1461"])
    run_purchasing_checks(ctx, [])
    assert "PUR.INTERNAL_NORM" not in codes(ctx)


def test_sonderblechdicke(tmp_path):
    ctx = make_ctx(tmp_path, ["Blechdicke 4,7 mm", "Blech gekantet"])
    run_purchasing_checks(ctx, [])
    assert "PUR.STOCK_SIZE" in codes(ctx)


def test_lagerblechdicke_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["Blechdicke 5,0 mm", "Blech gekantet"])
    run_purchasing_checks(ctx, [])
    assert "PUR.STOCK_SIZE" not in codes(ctx)


# ------------------------------------------------- Bemaßungswidersprüche
def test_vertauschte_grenzabmasse(tmp_path):
    ctx = make_ctx(tmp_path, ["x"])
    dim = _dim(40.0, tol_plus=-0.2, tol_minus=0.1)
    check_tolerance_order(ctx, [dim])
    assert "DIM.TOL_ORDER" in codes(ctx)


def test_korrekte_grenzabmasse_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["x"])
    check_tolerance_order(ctx, [_dim(40.0, tol_plus=0.2, tol_minus=-0.1)])
    assert not codes(ctx)


def test_ted_mit_toleranz(tmp_path):
    ctx = make_ctx(tmp_path, ["x"])
    check_tolerance_order(ctx, [_dim(40.0, is_basic=True, tol_plus=0.1,
                                     tol_minus=-0.1)])
    assert "DIM.BASIC_TOL" in codes(ctx)


def test_rauheit_zu_grob_fuer_toleranz(tmp_path):
    ctx = make_ctx(tmp_path, ["Rz 63"])
    check_roughness_vs_tolerance(ctx, [_dim(20.0, fit="H7")])
    assert "SURF.TOL_MISMATCH" in codes(ctx)


def test_passende_rauheit_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["Rz 4"])
    check_roughness_vs_tolerance(ctx, [_dim(20.0, fit="H7")])
    assert not codes(ctx)


# --------------------------------------------------- Wasserstoffversprödung
def test_galvanisch_auf_hochfest_ohne_entsproedung(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff 42CrMo4", "Haerte 45 HRC",
                              "galvanisch verzinkt nach ISO 2081"])
    check_hydrogen_embrittlement(ctx)
    assert "COAT.EMBRITTLEMENT" in codes(ctx)


def test_galvanisch_mit_entsproedung_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff 42CrMo4", "Haerte 45 HRC",
                              "galvanisch verzinkt nach ISO 2081",
                              "wasserstoffarm gegluht nach EN ISO 4042"])
    check_hydrogen_embrittlement(ctx)
    assert not codes(ctx)


def test_galvanisch_auf_baustahl_ohne_meldung(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff S235JR", "galvanisch verzinkt"])
    check_hydrogen_embrittlement(ctx)
    assert not codes(ctx)
