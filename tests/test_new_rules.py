"""Tests der Praxisregeln: Eloxal-Legierung, Schweißbolzen/Verzinkung,
GD&T-Widersprüche, Positionsballone."""
from pathlib import Path

import pymupdf
import pytest

from drawing_checker.checks.base import CheckContext, load_profile
from drawing_checker.checks.drawing_checks import run_drawing_checks
from drawing_checker.core.models import PackageContent, Severity
from drawing_checker.drawing.pdfdoc import DrawingPdf

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def make_ctx(tmp_path: Path, lines, profile: str = "default") -> CheckContext:
    """Zeilen als (x, text) oder nur text (dann Standardspalte links)."""
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    kwargs = {}
    if Path(FONT).exists():
        page.insert_font(fontname="T", fontfile=FONT)
        kwargs["fontname"] = "T"
    lines = list(lines) + ["Interne Testzeichnung – Blatt 1 von 1, Stand 2026"]
    for i, line in enumerate(lines):
        x, text = line if isinstance(line, tuple) else (40, line)
        page.insert_text((x, 60 + i * 30), text, fontsize=10, **kwargs)
    path = tmp_path / "t.pdf"
    doc.save(path)
    doc.close()
    return CheckContext("123", DrawingPdf(path), PackageContent(),
                        load_profile(profile))


def codes(ctx) -> dict:
    run_drawing_checks(ctx)
    return {f.code: f for f in ctx.findings}


# ------------------------------------------------ Eloxal-Legierungswahl
def test_cast_alloy_anodized_is_error(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff: AlSi10Mg", "schwarz eloxiert"]))
    assert c["MAT.ANODIZE_ALLOY"].severity == Severity.ERROR


def test_alcu_alloy_anodized_is_error(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff EN AW-2007", "eloxiert natur"]))
    assert "MAT.ANODIZE_ALLOY" in c


def test_7075_anodized_is_warning(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff EN AW-7075", "anodized type II"]))
    assert c["MAT.ANODIZE_ALLOY"].severity == Severity.WARNING


def test_6082_anodized_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff EN AW-6082", "eloxiert 15 µm"]))
    assert "MAT.ANODIZE_ALLOY" not in c


# ---------------------------------------- Schweißbolzen auf Verzinkung
def test_stud_weld_on_galvanized_is_error(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff: S235JR",
        "Blech feuerverzinkt nach ISO 1461",
        "4x Schweißbolzen M8 ISO 13918",
    ]))
    assert c["PROC.STUD_ON_ZINC"].severity == Severity.ERROR


def test_weld_and_zinc_without_sequence_is_warning(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff: S355J2", "Naht a4 umlaufend, ISO 5817-C",
        "Baugruppe feuerverzinkt",
    ]))
    assert c["PROC.WELD_ZINC_ORDER"].severity == Severity.WARNING


def test_weld_and_zinc_with_sequence_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff: S355J2", "Naht a4 umlaufend, ISO 5817-C",
        "Nach dem Schweißen komplett feuerverzinken (ISO 1461)",
    ]))
    assert "PROC.WELD_ZINC_ORDER" not in c
    assert "PROC.STUD_ON_ZINC" not in c


# ---------------------------------------------------- GD&T-Widersprüche
def test_form_tolerance_with_datum_is_error(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff C45", "⏥ 0,1 A"]))
    assert c["GPS.FORM_WITH_DATUM"].severity == Severity.ERROR


def test_form_tolerance_without_datum_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff C45", "⏥ 0,1", "○ 0,05"]))
    assert "GPS.FORM_WITH_DATUM" not in c


def test_deprecated_concentricity_symbol_warns(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff C45", "◎ ⌀0,2 A", "Bezug A"]))
    assert c["GPS.DEPRECATED_SYMBOL"].severity == Severity.WARNING


# ------------------------------------------------------ Positionsballone
BOM = [
    (600, "Stückliste"),
    (600, "Pos. Menge Benennung"),
    (600, "1 2 Grundplatte"),
    (600, "2 1 Rippe"),
]


def test_bom_without_balloons_warns(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff S235JR"] + BOM))
    assert c["DOC.BALLOONS"].severity == Severity.WARNING


def test_bom_with_balloons_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff S235JR",
        (100, "1"), (150, "2"),   # Ballon-Nummern an den Teilen
    ] + BOM))
    assert "DOC.BALLOONS" not in c


def test_no_bom_no_balloon_check(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff S235JR", "Einzelteil"]))
    assert "DOC.BALLOONS" not in c


# ------------------------------------ Beschichtung vs. Passung/Gewinde
def test_zinc_with_fit_warns(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff S355J2", "Bohrung ⌀22 H7", "feuerverzinkt ISO 1461"]))
    assert c["COAT.FIT"].severity == Severity.WARNING


def test_zinc_with_fit_and_note_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff S355J2", "Bohrung ⌀22 H7",
        "feuerverzinkt ISO 1461, Passung H7 nach dem Verzinken nachreiben"]))
    assert "COAT.FIT" not in c


def test_anodize_with_thread_warns(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff EN AW-6082", "Gewinde M8", "schwarz eloxiert"]))
    assert "COAT.FIT" in c


def test_zinc_without_fit_no_warning(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff S235JR", "feuerverzinkt"]))
    assert "COAT.FIT" not in c


# ------------------------------------------------ Brünieren auf Nichtstahl
def test_blackening_on_stainless_conflict(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff 1.4301", "brüniert"]))
    assert "MAT.COATING_CONFLICT" in c


def test_blackening_on_steel_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff C45", "brüniert"]))
    assert "MAT.COATING_CONFLICT" not in c


# ------------------------------------------------------ Mischverbindungen
def test_alu_plus_steel_welded_is_error(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Pos 1: S235JR", "Pos 2: EN AW-5754", "geschweißt nach ISO 5817-C"]))
    assert c["WELD.MIXED"].severity == Severity.ERROR


def test_stainless_plus_steel_needs_filler(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Pos 1: S355J2", "Pos 2: 1.4301", "Naht a3 umlaufend"]))
    assert c["WELD.MIXED_FILLER"].severity == Severity.WARNING


def test_stainless_plus_steel_with_309_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Pos 1: S355J2", "Pos 2: 1.4301",
        "Naht a3 umlaufend, Zusatzwerkstoff 309L"]))
    assert "WELD.MIXED_FILLER" not in c


# --------------------------------------- Schweißteil nur mit ISO 2768
def test_weld_with_only_2768_warns(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff S355J2", "geschweißt ISO 5817-C",
        "Allgemeintoleranzen ISO 2768-mK"]))
    assert c["NORM.WELD_GENTOL"].severity == Severity.WARNING


def test_weld_with_13920_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff S355J2", "geschweißt ISO 5817-C",
        "Allgemeintoleranzen ISO 2768-mK und ISO 13920-BF"]))
    assert "NORM.WELD_GENTOL" not in c


# -------------------------------------------- Gewinde mit Passungsklasse
def test_thread_with_fit_class_is_error(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff C45", "Gewinde M12 H7"]))
    assert c["THRD.FIT_CLASS"].severity == Severity.ERROR


def test_thread_with_correct_class_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff C45", "Gewinde M12 - 6H"]))
    assert "THRD.FIT_CLASS" not in c
