"""Tests für Werkstofferkennung und fachliche Widerspruchsprüfung.

Die Prüf-PDFs werden zur Laufzeit aus Textzeilen gebaut (echte PDFs mit
Textlayer), damit exakt derselbe Extraktionspfad wie in Produktion läuft.
"""
from pathlib import Path

import pymupdf
import pytest

from drawing_checker.checks.base import CheckContext, load_profile
from drawing_checker.checks.materials import (
    find_materials, run_material_checks,
)
from drawing_checker.core.models import PackageContent, Severity
from drawing_checker.drawing.pdfdoc import DrawingPdf

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def make_ctx(tmp_path: Path, lines: list[str],
             profile: str = "default") -> CheckContext:
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    kwargs = {}
    if Path(FONT).exists():
        page.insert_font(fontname="T", fontfile=FONT)
        kwargs["fontname"] = "T"
    # Füllzeile, damit die Seite sicher als "hat Textlayer" erkannt wird.
    lines = lines + ["Interne Testzeichnung – Blatt 1 von 1, Ausgabestand 2026"]
    for i, line in enumerate(lines):
        page.insert_text((40, 60 + i * 30), line, fontsize=10, **kwargs)
    path = tmp_path / "t.pdf"
    doc.save(path)
    doc.close()
    pdf = DrawingPdf(path)
    return CheckContext(material="123", pdf=pdf, package=PackageContent(),
                        profile=load_profile(profile))


def codes(ctx) -> dict[str, object]:
    run_material_checks(ctx)
    return {f.code: f for f in ctx.findings}


# ------------------------------------------------------------- Erkennung
def test_find_material_variants(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: 1.4305", "alternativ X5CrNi18-10"])
    names = [h.material.name for h in find_materials(ctx)]
    assert "1.4305 (X8CrNiS18-9)" in names
    assert "1.4301 (X5CrNi18-10)" in names


def test_material_missing(tmp_path):
    ctx = make_ctx(tmp_path, ["Maßstab 1:2", "Allgemeintoleranzen ISO 2768-mK"])
    c = codes(ctx)
    assert "MAT.MISSING" in c
    assert c["MAT.MISSING"].severity == Severity.ERROR


def test_material_label_but_unknown(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: Unobtainium X99"])
    c = codes(ctx)
    assert c["MAT.MISSING"].severity == Severity.WARNING


def test_material_present_no_finding(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: S355J2+N"])
    assert "MAT.MISSING" not in codes(ctx)


# ---------------------------------------------------- Widerspruch Schweißen
def test_1_4305_with_weld_is_conflict(tmp_path):
    ctx = make_ctx(tmp_path, [
        "Werkstoff: 1.4305",
        "Schweißnaht a4 umlaufend, ISO 5817-C",
    ])
    c = codes(ctx)
    assert "MAT.WELD_CONFLICT" in c
    assert c["MAT.WELD_CONFLICT"].severity == Severity.ERROR
    assert "1.4305" in c["MAT.WELD_CONFLICT"].text


def test_s355_with_weld_is_fine(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: S355J2", "a4 ISO 5817-B umlaufend"])
    assert "MAT.WELD_CONFLICT" not in codes(ctx)


def test_42crmo4_weld_is_limited_warning(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: 42CrMo4 +QT", "geschweißt nach ISO 5817-B"])
    c = codes(ctx)
    assert c["MAT.WELD_CONFLICT"].severity == Severity.WARNING


def test_gg25_weld_conflict(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff EN-GJL-250", "Naht a3 ringsum"])
    assert "MAT.WELD_CONFLICT" in codes(ctx)


# ---------------------------------------------- Widerspruch Wärmebehandlung
def test_s235_hardened_is_conflict(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: S235JR", "Oberfläche gehärtet 55 HRC"])
    assert "MAT.HT_CONFLICT" in codes(ctx)


def test_c45_hardened_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: C45E", "gehärtet und angelassen"])
    assert "MAT.HT_CONFLICT" not in codes(ctx)


def test_16mncr5_case_hardened_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff 16MnCr5", "einsatzgehärtet Eht 0,8"])
    assert "MAT.HT_CONFLICT" not in codes(ctx)


def test_pa6_heat_treatment_nonsense(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: PA6 GF30", "vergütet"])
    assert "MAT.HT_CONFLICT" in codes(ctx)


# --------------------------------------------------- Widerspruch Beschichtung
def test_stainless_galvanized_conflict(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: 1.4301", "feuerverzinkt nach ISO 1461"])
    assert "MAT.COATING_CONFLICT" in codes(ctx)


def test_steel_anodized_conflict(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: S355J2", "schwarz eloxiert"])
    assert "MAT.COATING_CONFLICT" in codes(ctx)


def test_alu_anodized_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff EN AW-6082", "natur eloxiert 15 µm"])
    assert "MAT.COATING_CONFLICT" not in codes(ctx)


# --------------------------------------------------------- Norm vs. Werkstoff
def test_alu_with_iso5817_mismatch(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff EN AW-5754", "Schweißnahtgüte ISO 5817-C"])
    assert "NORM.MATERIAL_MISMATCH" in codes(ctx)


def test_steel_with_iso10042_mismatch(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Nahtgüte ISO 10042-B"])
    assert "NORM.MATERIAL_MISMATCH" in codes(ctx)


# -------------------------------------------------------------- Guss-Kontext
def test_cast_context_without_cast_material(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff: C45", "Gussteil nach ISO 8062-3 DCTG12"])
    assert "MAT.CAST_CONFLICT" in codes(ctx)


def test_cast_context_with_gjs_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff EN-GJS-400-15", "Gusstoleranzen ISO 8062"])
    assert "MAT.CAST_CONFLICT" not in codes(ctx)


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
    assert "NORM.OBSOLETE" not in codes(ctx)
