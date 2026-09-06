"""Vertiefte Geometrieprüfungen: Masse, Bohrbild, Gewinde, Maßextraktion."""
from pathlib import Path

import pymupdf
import pytest

from drawing_checker.checks.base import CheckContext, load_profile
from drawing_checker.checks.geometry_checks import (
    check_hole_pattern, check_mass, check_threads,
)
from drawing_checker.checks.step_compare import StepGeometry, analyze_step
from drawing_checker.core.models import BBox, PackageContent, Severity
from drawing_checker.drawing.dimensions import (
    DimKind, DimValue, hole_pattern, it_grade_span,
)
from drawing_checker.drawing.metadata import extract_weight_kg
from drawing_checker.drawing.pdfdoc import DrawingPdf

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
pytest.importorskip("OCP", reason="Geometrieprüfung benötigt OpenCascade")


def make_ctx(tmp_path: Path, lines, profile="default") -> CheckContext:
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    kwargs = {}
    if Path(FONT).exists():
        page.insert_font(fontname="T", fontfile=FONT)
        kwargs["fontname"] = "T"
    lines = list(lines) + ["Interne Testzeichnung – Blatt 1 von 1"]
    for i, line in enumerate(lines):
        page.insert_text((40, 60 + i * 30), line, fontsize=10, **kwargs)
    path = tmp_path / "t.pdf"
    doc.save(path)
    doc.close()
    return CheckContext("123", DrawingPdf(path), PackageContent(),
                        load_profile(profile))


def dv(value, kind=DimKind.DIAMETER, count=1):
    return DimValue(value=value, kind=kind, raw=str(value),
                    bbox=BBox(0, 0, 1, 1), page=0, count=count)


# --------------------------------------------------------- STEP-Analyse
def test_bracket_holes_detected(mock_dir):
    geo = analyze_step(mock_dir / "_arbeit" / "M_10473215.stp")
    assert geo.holes.get(18.0) == 4       # 4 Befestigungsbohrungen
    assert geo.holes.get(22.0) == 1       # Kopfbohrung
    assert not geo.shafts                 # Konsole hat keine Außenzylinder


def test_shaft_steps_detected_as_shafts(mock_dir):
    geo = analyze_step(mock_dir / "_arbeit" / "M_10473217.stp")
    assert set(geo.shafts) >= {70.0, 55.0, 45.0, 40.0}
    assert not geo.holes


def test_mass_from_volume_and_density(mock_dir):
    geo = analyze_step(mock_dir / "_arbeit" / "M_10473217.stp")
    assert geo.mass_kg(7.85) == pytest.approx(7.4, abs=0.2)
    assert geo.mass_kg(0) is None


# ---------------------------------------------------- Gewichtsextraktion
def test_weight_units(tmp_path):
    for text, expect in [("Gewicht 18,4 kg", 18.4), ("Weight 950 g", 0.95),
                         ("Masse 1,2 t", 1200.0)]:
        ctx = make_ctx(tmp_path, [text])
        assert extract_weight_kg(ctx.pdf) == pytest.approx(expect)


def test_weight_prefers_labelled_value(tmp_path):
    ctx = make_ctx(tmp_path, ["Zusatz 3 kg Beilage", "Gewicht / Weight 42,5 kg"])
    assert extract_weight_kg(ctx.pdf) == pytest.approx(42.5)


def test_no_weight_returns_none(tmp_path):
    assert extract_weight_kg(make_ctx(tmp_path, ["ohne Angabe"]).pdf) is None


# ----------------------------------------------------------- Masse-Check
def test_mass_mismatch_is_error(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Gewicht 30,0 kg"])
    geo = StepGeometry(obb_dims=(200, 100, 50), volume=1_000_000,
                       backend="occ")           # 1000 cm³ × 7,85 = 7,85 kg
    summary = check_mass(ctx, geo)
    codes = {f.code: f for f in ctx.findings}
    assert codes["GEO.MASS"].severity == Severity.ERROR
    assert "kg" in summary


def test_mass_match_no_finding(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Gewicht 7,9 kg"])
    geo = StepGeometry(obb_dims=(200, 100, 50), volume=1_000_000,
                       backend="occ")
    check_mass(ctx, geo)
    assert not [f for f in ctx.findings if f.code.startswith("GEO.MASS")]


def test_mass_minor_deviation_is_warning(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Gewicht 9,5 kg"])
    geo = StepGeometry(obb_dims=(200, 100, 50), volume=1_000_000,
                       backend="occ")          # 7,85 kg -> 17 % Abweichung
    check_mass(ctx, geo)
    assert ctx.findings[0].severity == Severity.WARNING


def test_mass_guss_profile_more_tolerant(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff EN-GJS-400-15", "Gewicht 9,0 kg"],
                   profile="guss")
    geo = StepGeometry(obb_dims=(200, 100, 50), volume=1_000_000,
                       backend="occ")          # 7,1 kg -> 21 % Abweichung
    check_mass(ctx, geo)
    assert not ctx.findings   # unter der Guss-Warnschwelle von 25 %


def test_mass_needs_occ_backend(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Gewicht 30 kg"])
    geo = StepGeometry(obb_dims=(200, 100, 50), volume=1_000_000,
                       backend="fallback")
    assert check_mass(ctx, geo) == ""
    assert not ctx.findings


# -------------------------------------------------------- Bohrbild-Check
def test_hole_count_missing_is_error(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff S235JR", "4×⌀18"])
    geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                       holes={12.0: 2})
    check_hole_pattern(ctx, geo, [dv(18, count=4)])
    codes = {f.code: f for f in ctx.findings}
    assert codes["GEO.HOLE_COUNT"].severity == Severity.ERROR


def test_hole_count_partial_is_warning(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff S235JR"])
    geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                       holes={18.0: 2})
    check_hole_pattern(ctx, geo, [dv(18, count=4)])
    assert ctx.findings[0].severity == Severity.WARNING


def test_hole_count_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff S235JR"])
    geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                       holes={18.0: 4})
    check_hole_pattern(ctx, geo, [dv(18, count=4)])
    assert not ctx.findings


def test_single_diameter_is_not_counted(tmp_path):
    """Einzelnennungen ohne Multiplikator lösen keinen Zählabgleich aus."""
    ctx = make_ctx(tmp_path, ["Werkstoff S235JR"])
    geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                       holes={})
    assert check_hole_pattern(ctx, geo, [dv(18), dv(18)]) == ""
    assert not ctx.findings


def test_hole_pattern_from_dimensions():
    assert hole_pattern([dv(18, count=4), dv(18, count=2), dv(9)]) == {
        18.0: 6, 9.0: 1}


# --------------------------------------------------------- Gewinde-Check
def test_thread_without_core_hole(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff C45", "Gewinde M12"])
    geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                       holes={30.0: 1})
    check_threads(ctx, geo, [dv(12, kind=DimKind.THREAD)])
    assert ctx.findings[0].code == "GEO.THREAD"


def test_thread_with_core_hole_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff C45"])
    geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                       holes={10.2: 4})
    check_threads(ctx, geo, [dv(12, kind=DimKind.THREAD)])
    assert not ctx.findings


def test_thread_with_clearance_hole_ok(tmp_path):
    """Gewinde im Modell oft als glatte Bohrung im Nennmaß dargestellt."""
    ctx = make_ctx(tmp_path, ["Werkstoff C45"])
    geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                       holes={12.0: 2})
    check_threads(ctx, geo, [dv(12, kind=DimKind.THREAD)])
    assert not ctx.findings


# ----------------------------------------------- Maßextraktion: Toleranzen
def test_it_grade_spans():
    assert it_grade_span("H7", 40) == pytest.approx(0.025)
    assert it_grade_span("h6", 40) == pytest.approx(0.016)
    assert it_grade_span("js9", 100) == pytest.approx(0.087)
    assert it_grade_span("", 40) is None


def test_dimension_tolerance_span():
    d = DimValue(40, DimKind.LINEAR, "40", BBox(0, 0, 1, 1), 0,
                 tol_plus=0.2, tol_minus=-0.1)
    assert d.tolerance_span == pytest.approx(0.3)
    f = DimValue(40, DimKind.DIAMETER, "⌀40H7", BBox(0, 0, 1, 1), 0, fit="H7")
    assert f.tolerance_span == pytest.approx(0.025)
    assert f.it_grade == 7


# ------------------------------------------------------ E2E-Regression
def test_wrong_config_has_three_independent_indications(mock_dir, tmp_path):
    """Falsches Gussgehäuse: Hüllmaß, Masse und Bohrbild schlagen an."""
    from drawing_checker.core.models import RunConfig
    from drawing_checker.core.orchestrator import Callbacks, Orchestrator
    from drawing_checker.sap.mock import MockSapAdapter

    cfg = RunConfig(excel_path=mock_dir / "Materialliste_Mock.xlsx",
                    sheet_name="Materialliste", material_column="C",
                    header_row=1, output_dir=tmp_path / "erg")
    adapter = MockSapAdapter(mock_dir)
    adapter.ensure_ready()
    orch = Orchestrator(cfg, adapter, Callbacks())
    orch.start(); orch.join(300)
    res = {r.material: r for r in orch.state.results.values()}
    wrong = {f.code for f in res["10473216"].findings}
    assert {"GEO.MISMATCH", "GEO.MASS", "GEO.HOLE_COUNT"} <= wrong
    # Korrekte Teile bleiben frei von Geometrie-Findings
    for ok_material in ("10473215", "10473217"):
        codes = {f.code for f in res[ok_material].findings}
        assert not [c for c in codes if c.startswith("GEO.")]
