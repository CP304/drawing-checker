"""Maßstabsextraktion und maßstabsbasierte Prüfungen."""
from pathlib import Path

import pymupdf
import pytest

from drawing_checker.checks.base import CheckContext, load_profile
from drawing_checker.checks.scale_checks import (
    check_scale_consistency, check_view_vs_model,
)
from drawing_checker.checks.step_compare import StepGeometry
from drawing_checker.core.models import BBox, PackageContent, Severity
from drawing_checker.drawing.dimensions import DimKind, DimValue
from drawing_checker.drawing.metadata import extract_scale, mm_per_point
from drawing_checker.drawing.pdfdoc import DrawingPdf

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
ECHT = Path(__file__).resolve().parent.parent / "mockdata" / "echt_quellen"


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
    from drawing_checker.checks.scale_checks import measure_largest_view

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
    import drawing_checker.checks.scale_checks as sc

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
    import drawing_checker.checks.scale_checks as sc

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
