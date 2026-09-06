import pytest

from drawing_checker.checks.base import load_profile
from drawing_checker.checks.step_compare import (
    StepGeometry, _analyze_pointcloud, analyze_step, compare_step_to_drawing,
)
from drawing_checker.core.models import BBox
from drawing_checker.drawing.dimensions import DimKind, DimValue


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
    from drawing_checker.checks.step_compare import _box_bounds

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
