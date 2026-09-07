"""Tests der Ausbaustufe Konturprojektion (STEP-Silhouetten vs. PDF-Ansichten)."""
from pathlib import Path

import pytest

from drawing_checker.pruef_geometrie import ( SCORE_BAD, SCORE_GOOD, compare_contours, extract_views, project_step_silhouettes, )
from drawing_checker.zeichnung import DrawingPdf

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
