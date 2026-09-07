"""Tests der Regeln aus Runde 3: Masse-Plausibilität, Dokumenten-Formalien,
internationale Beschaffung, Bemaßungswidersprüche, Wasserstoffversprödung.

Zu jeder Regel ein Positiv- und ein Negativfall (Konvention aus CLAUDE.md).
"""
from pathlib import Path

import pymupdf

from drawing_checker.regeln import CheckContext, load_profile
from drawing_checker.pruef_bemassung import ( check_roughness_vs_tolerance, check_tolerance_order, )
from drawing_checker.pruef_zeichnung import run_doc_checks
from drawing_checker.pruef_werkstoff import ( check_density_hint, check_mass_plausibility, )
from drawing_checker.pruef_werkstoff import check_hydrogen_embrittlement
from drawing_checker.pruef_werkstoff import run_purchasing_checks
from drawing_checker.kern import BBox, PackageContent, Severity
from drawing_checker.zeichnung import ( DimKind, DimValue, extract_dimensions, )
from drawing_checker.zeichnung import DrawingPdf

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def make_ctx(tmp_path: Path, lines, profile: str = "default",
             pages: int = 1, name: str = "t.pdf") -> CheckContext:
    doc = pymupdf.open()
    for pno in range(pages):
        page = doc.new_page(width=842, height=595)
        kwargs = {}
        if Path(FONT).exists():
            page.insert_font(fontname="T", fontfile=FONT)
            kwargs["fontname"] = "T"
        if pno == 0:
            # Fülltext: unter 40 Zeichen gilt das PDF als "ohne Textlayer".
            lines = list(lines) + [
                "Pruefzeichnung fuer den automatischen Regeltest, Ausgabe A"]
            for i, text in enumerate(lines):
                page.insert_text((40, 60 + i * 25), text, fontsize=10, **kwargs)
    path = tmp_path / name
    doc.save(path)
    doc.close()
    return CheckContext("123", DrawingPdf(path), PackageContent(),
                        load_profile(profile))


def dims_of(ctx) -> list[DimValue]:
    return extract_dimensions(ctx.pdf, 6000)


def codes(ctx) -> set[str]:
    return {f.code for f in ctx.findings}


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
