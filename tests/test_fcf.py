"""Toleranzrahmen-Erkennung (Feature Control Frames) als Vektorgrafik.

Nutzt die echten Kalibrierzeichnungen aus mockdata/echt_quellen – nur dort
liegen Toleranzrahmen so vor wie in der Praxis (Grafik statt Textsymbol).
"""
from pathlib import Path

import pytest

from drawing_checker.checks.base import CheckContext, load_profile
from drawing_checker.checks.gps_checks import (
    check_diameter_zone_needs_datum, check_gdt_readability,
)
from drawing_checker.core.models import BBox, PackageContent, Severity
from drawing_checker.drawing.fcf import FeatureFrame, find_feature_frames
from drawing_checker.drawing.pdfdoc import DrawingPdf

ECHT = Path(__file__).resolve().parent.parent / "mockdata" / "echt_quellen"
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
