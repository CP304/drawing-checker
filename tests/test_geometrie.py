"""Abgleich gegen das STEP-Modell: Masse, Bohrbild, Spiegelung, Silhouette.
"""
from __future__ import annotations

# ======================================================================
# step_compare
# ======================================================================
import pytest

from drawing_checker.regeln import load_profile
from drawing_checker.pruef_geometrie import ( StepGeometry, _analyze_pointcloud, analyze_step, compare_step_to_drawing, )
from drawing_checker.kern import BBox
from drawing_checker.zeichnung import DimKind, DimValue


def dv(value, kind=DimKind.LINEAR):
    return DimValue(value, kind, str(value), BBox(0, 0, 1, 1), 0)


@pytest.fixture(scope="module")
def profile():
    return load_profile("default")


def test_occ_analysis_on_shaft(mock_dir):
    geo = analyze_step(mock_dir / "_arbeit" / "M_10473217.stp")
    assert geo.obb_dims[0] == pytest.approx(420, abs=1)
    assert geo.obb_dims[1] == pytest.approx(70, abs=1)
    if geo.backend == "occ":
        assert 70.0 in geo.cylinder_diameters
        assert geo.volume > 0


def test_pointcloud_fallback_on_shaft(mock_dir):
    geo = _analyze_pointcloud(mock_dir / "_arbeit" / "M_10473217.stp")
    assert geo.backend == "fallback"
    assert geo.obb_dims[0] == pytest.approx(420, abs=2)


def test_matching_geometry_passes(profile):
    geo = StepGeometry(obb_dims=(420.0, 70.0, 70.0),
                       cylinder_diameters=[70.0, 55.0, 45.0, 40.0])
    dims = [dv(420), dv(120), dv(90), dv(70, DimKind.DIAMETER),
            dv(55, DimKind.DIAMETER)]
    res = compare_step_to_drawing(geo, dims, profile)
    assert res.verdict == "passt"


def test_wrong_config_detected_by_diagonal(profile):
    # Zeichnung 330 lang, STEP nur 200 -> Maß größer als Raumdiagonale
    geo = StepGeometry(obb_dims=(200.0, 140.0, 120.0))
    dims = [dv(330), dv(280), dv(180)]
    res = compare_step_to_drawing(geo, dims, profile)
    assert res.verdict == "passt_nicht"


def test_no_dims_is_uncertain(profile):
    geo = StepGeometry(obb_dims=(100.0, 50.0, 20.0))
    res = compare_step_to_drawing(geo, [], profile)
    assert res.verdict == "unsicher"


def test_guss_profile_is_more_tolerant():
    guss = load_profile("guss")
    default = load_profile("default")
    geo = StepGeometry(obb_dims=(255.0, 180.0, 120.0))  # 25 mm unter Nennmaß
    dims = [dv(280), dv(180), dv(120)]
    assert compare_step_to_drawing(geo, dims, guss).verdict == "passt"
    assert compare_step_to_drawing(geo, dims, default).verdict != "passt"


# --------------------------------------------- OCP-Fassungsunabhaengigkeit
def test_box_bounds_kommt_mit_beiden_ocp_fassungen_klar():
    """OCP 7.9 (Python 3.10) und OCP 8.x benennen die Bnd_Box anders.

    7.9 kennt nur CornerMin()/CornerMax(), 8.x zusätzlich GetXMin().
    Beides muss dieselben Werte liefern, sonst läuft das Werkzeug je nach
    Python-Fassung des Zielrechners nicht.
    """
    from drawing_checker.pruef_geometrie import _box_bounds

    class _Punkt:
        def __init__(self, x, y, z):
            self._w = (x, y, z)

        def X(self):
            return self._w[0]

        def Y(self):
            return self._w[1]

        def Z(self):
            return self._w[2]

    class _Alt:            # OCP 7.9
        def CornerMin(self):
            return _Punkt(1, 2, 3)

        def CornerMax(self):
            return _Punkt(4, 5, 6)

    class _Neu:            # OCP 8.x ohne CornerMin
        def GetXMin(self):
            return 1

        def GetYMin(self):
            return 2

        def GetZMin(self):
            return 3

        def GetXMax(self):
            return 4

        def GetYMax(self):
            return 5

        def GetZMax(self):
            return 6

    assert _box_bounds(_Alt()) == (1, 2, 3, 4, 5, 6)
    assert _box_bounds(_Neu()) == (1, 2, 3, 4, 5, 6)


# ======================================================================
# geometry_deep
# ======================================================================
# Vertiefte Geometrieprüfungen: Masse, Bohrbild, Gewinde, Maßextraktion.
from pathlib import Path

import pymupdf

from drawing_checker.regeln import CheckContext, load_profile
from drawing_checker.pruef_geometrie import ( check_hole_pattern, check_mass, check_threads, )
from drawing_checker.pruef_geometrie import StepGeometry, analyze_step
from drawing_checker.kern import BBox, PackageContent, Severity
from drawing_checker.zeichnung import ( DimKind, DimValue, hole_pattern, it_grade_span, )
from drawing_checker.zeichnung import extract_weight_kg
from drawing_checker.zeichnung import DrawingPdf
from conftest import FONT, make_ctx

pytest.importorskip("OCP", reason="Geometrieprüfung benötigt OpenCascade")




def dv_dia(value, kind=DimKind.DIAMETER, count=1):
    return DimValue(value=value, kind=kind, raw=str(value),
                    bbox=BBox(0, 0, 1, 1), page=0, count=count)


# --------------------------------------------------------- STEP-Analyse
def test_bracket_holes_detected(mock_dir):
    geo = analyze_step(mock_dir / "_arbeit" / "M_10473215.stp")
    assert geo.solid_count == 1 and geo.disjoint_solids == 1
    assert geo.holes.get(18.0) == 4       # 4 Befestigungsbohrungen
    assert geo.holes.get(16.0) == 1       # Kopfbohrung im Steg
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
    check_hole_pattern(ctx, geo, [dv_dia(18, count=4)])
    codes = {f.code: f for f in ctx.findings}
    assert codes["GEO.HOLE_COUNT"].severity == Severity.ERROR


def test_hole_count_partial_is_warning(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff S235JR"])
    geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                       holes={18.0: 2})
    check_hole_pattern(ctx, geo, [dv_dia(18, count=4)])
    assert ctx.findings[0].severity == Severity.WARNING


def test_hole_count_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff S235JR"])
    geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                       holes={18.0: 4})
    check_hole_pattern(ctx, geo, [dv_dia(18, count=4)])
    assert not ctx.findings


def test_single_diameter_is_not_counted(tmp_path):
    """Einzelnennungen ohne Multiplikator lösen keinen Zählabgleich aus."""
    ctx = make_ctx(tmp_path, ["Werkstoff S235JR"])
    geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                       holes={})
    assert check_hole_pattern(ctx, geo, [dv_dia(18), dv_dia(18)]) == ""
    assert not ctx.findings


def test_hole_pattern_from_dimensions():
    assert hole_pattern([dv_dia(18, count=4), dv_dia(18, count=2), dv_dia(9)]) == {
        18.0: 6, 9.0: 1}


# --------------------------------------------------------- Gewinde-Check
def test_thread_without_core_hole(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff C45", "Gewinde M12"])
    geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                       holes={30.0: 1})
    check_threads(ctx, geo, [dv_dia(12, kind=DimKind.THREAD)])
    assert ctx.findings[0].code == "GEO.THREAD"


def test_thread_with_core_hole_ok(tmp_path):
    ctx = make_ctx(tmp_path, ["Werkstoff C45"])
    geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                       holes={10.2: 4})
    check_threads(ctx, geo, [dv_dia(12, kind=DimKind.THREAD)])
    assert not ctx.findings


def test_thread_with_clearance_hole_ok(tmp_path):
    """Gewinde im Modell oft als glatte Bohrung im Nennmaß dargestellt."""
    ctx = make_ctx(tmp_path, ["Werkstoff C45"])
    geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                       holes={12.0: 2})
    check_threads(ctx, geo, [dv_dia(12, kind=DimKind.THREAD)])
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
    from drawing_checker.kern import RunConfig
    from drawing_checker.ablauf import Callbacks, Orchestrator
    from drawing_checker.sap_ymatdocs import MockSapAdapter

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


# ------------------------------------------- Einheiten und Baugruppe
def test_inch_mm_mismatch_detected(tmp_path):
    """Modell in Zoll exportiert: Zeichnungsmaß / OBB ≈ 25,4."""
    from drawing_checker.pruef_geometrie import check_unit_mismatch

    ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Länge 254"])
    geo = StepGeometry(obb_dims=(10.0, 4.0, 2.0), volume=80, backend="occ")
    assert check_unit_mismatch(ctx, geo, [dv_dia(254, kind=DimKind.LINEAR)])
    assert ctx.findings[0].code == "GEO.UNIT_MISMATCH"
    assert ctx.findings[0].severity == Severity.ERROR


def test_matching_units_no_finding(tmp_path):
    from drawing_checker.pruef_geometrie import check_unit_mismatch

    ctx = make_ctx(tmp_path, ["Werkstoff S355J2"])
    geo = StepGeometry(obb_dims=(250.0, 100.0, 50.0), volume=1000,
                       backend="occ")
    assert not check_unit_mismatch(ctx, geo, [dv_dia(254, kind=DimKind.LINEAR)])
    assert not ctx.findings


def test_assembly_without_bom_is_error(tmp_path):
    from drawing_checker.pruef_geometrie import check_assembly_vs_part

    ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Einzelteil"])
    geo = StepGeometry(obb_dims=(200, 100, 50), volume=1000, backend="occ",
                       solid_count=3, disjoint_solids=3)
    check_assembly_vs_part(ctx, geo)
    assert ctx.findings[0].code == "GEO.ASSEMBLY"
    assert ctx.findings[0].severity == Severity.ERROR


def test_unfused_solids_are_info(tmp_path):
    """Sich berührende Körper sind ein Modellierungs-, kein Dokumentfehler."""
    from drawing_checker.pruef_geometrie import check_assembly_vs_part

    ctx = make_ctx(tmp_path, ["Werkstoff S355J2"])
    geo = StepGeometry(obb_dims=(200, 100, 50), volume=1000, backend="occ",
                       solid_count=2, disjoint_solids=1)
    check_assembly_vs_part(ctx, geo)
    assert ctx.findings[0].code == "GEO.NOT_FUSED"
    assert ctx.findings[0].severity == Severity.INFO


def test_single_solid_part_is_fine(tmp_path):
    from drawing_checker.pruef_geometrie import check_assembly_vs_part

    ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Einzelteil"])
    geo = StepGeometry(obb_dims=(200, 100, 50), volume=1000, backend="occ",
                       solid_count=1, disjoint_solids=1)
    check_assembly_vs_part(ctx, geo)
    assert not ctx.findings


# ======================================================================
# contour_projection
# ======================================================================
# Tests der Ausbaustufe Konturprojektion (STEP-Silhouetten vs. PDF-Ansichten).


from drawing_checker.pruef_geometrie import ( SCORE_BAD, SCORE_GOOD, compare_contours, extract_views, project_step_silhouettes, )

pytest.importorskip("OCP", reason="Konturprojektion benötigt OpenCascade")


@pytest.fixture(scope="module")
def shaft_pdf(mock_dir):
    with DrawingPdf(mock_dir / "_arbeit" / "Z_10473217.pdf") as pdf:
        yield pdf


def test_silhouettes_from_step(mock_dir):
    sil = project_step_silhouettes(mock_dir / "_arbeit" / "M_10473217.stp")
    assert len(sil) == 3
    assert all(len(s) > 10 for s in sil)
    # Eine Projektion muss das 420x70-Längsprofil sein
    spans = []
    for s in sil:
        xs = [c for seg in s for c in (seg[0], seg[2])]
        ys = [c for seg in s for c in (seg[1], seg[3])]
        spans.append(sorted([max(xs) - min(xs), max(ys) - min(ys)], reverse=True))
    assert any(abs(a - 420) < 2 and abs(b - 70) < 2 for a, b in spans)


def test_extract_views_filters_frame_and_dimensions(shaft_pdf):
    views = extract_views(shaft_pdf)
    assert 1 <= len(views) <= 4
    # ISO-128-Filter: Konturlinien sind deutlich weniger als alle Segmente
    assert views[0].all_count > len(views[0].segments)


def test_matching_pair_scores_good(mock_dir, shaft_pdf):
    r = compare_contours(shaft_pdf, mock_dir / "_arbeit" / "M_10473217.stp")
    assert r.views_used >= 1
    assert max(r.per_view) >= SCORE_GOOD


def test_wrong_pair_scores_low(mock_dir):
    with DrawingPdf(mock_dir / "_arbeit" / "Z_10473215.pdf") as bracket:
        wrong = compare_contours(bracket, mock_dir / "_arbeit" / "M_10473217.stp")
        right = compare_contours(bracket, mock_dir / "_arbeit" / "M_10473215.stp")
    assert wrong.score <= SCORE_BAD
    assert right.score >= SCORE_GOOD
    assert right.score > wrong.score + 0.2


def test_contour_stage_confirms_uncertain(mock_dir, shaft_pdf):
    """Ein 'unsicher' des Maßabgleichs wird durch gute Kontur bestätigt."""
    from drawing_checker.regeln import CheckContext, load_profile
    from drawing_checker.pruef_geometrie import ( CompareResult, StepGeometry, _apply_contour_stage, )
    from drawing_checker.kern import PackageContent

    ctx = CheckContext("x", shaft_pdf, PackageContent(), load_profile("default"))
    geometry = StepGeometry(obb_dims=(420.0, 70.0, 70.0), backend="occ")
    unsure = CompareResult("unsicher", "s", "d", main_ok=True)
    out = _apply_contour_stage(ctx, mock_dir / "_arbeit" / "M_10473217.stp",
                               unsure, geometry)
    assert out.verdict == "passt"
    assert "Kontur-Score" in out.summary


def test_contour_stage_never_overrides_mismatch(mock_dir, shaft_pdf):
    from drawing_checker.regeln import CheckContext, load_profile
    from drawing_checker.pruef_geometrie import ( CompareResult, StepGeometry, _apply_contour_stage, )
    from drawing_checker.kern import PackageContent

    ctx = CheckContext("x", shaft_pdf, PackageContent(), load_profile("default"))
    geometry = StepGeometry(obb_dims=(420.0, 70.0, 70.0), backend="occ")
    bad = CompareResult("passt_nicht", "s", "d")
    out = _apply_contour_stage(ctx, mock_dir / "_arbeit" / "M_10473217.stp",
                               bad, geometry)
    assert out.verdict == "passt_nicht"
    assert "Kontur-Score" not in out.summary  # Stufe läuft dann gar nicht


def test_contour_stage_disabled_by_profile(mock_dir, shaft_pdf, tmp_path,
                                           monkeypatch):
    d = tmp_path / "regeln"
    d.mkdir()
    (d / "profiles_aus.yaml").write_text(
        "profiles:\n  default:\n    rules:\n"
        "      GEO.CONTOUR: {enabled: false}\n", encoding="utf-8")
    monkeypatch.setenv("DRAWING_CHECKER_RULES", str(d))
    from drawing_checker.regeln import CheckContext, load_profile
    from drawing_checker.pruef_geometrie import ( CompareResult, StepGeometry, _apply_contour_stage, )
    from drawing_checker.kern import PackageContent

    ctx = CheckContext("x", shaft_pdf, PackageContent(), load_profile("default"))
    geometry = StepGeometry(obb_dims=(420.0, 70.0, 70.0), backend="occ")
    unsure = CompareResult("unsicher", "s", "d", main_ok=True)
    out = _apply_contour_stage(ctx, mock_dir / "_arbeit" / "M_10473217.stp",
                               unsure, geometry)
    assert out.verdict == "unsicher"
    assert "Kontur-Score" not in out.summary
