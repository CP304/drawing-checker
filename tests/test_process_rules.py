"""Verfahrensspezifische Vollständigkeit: Schweißen, Guss, Blech."""
from pathlib import Path

import pymupdf

from drawing_checker.checks.base import CheckContext, load_profile
from drawing_checker.checks.process_checks import run_process_checks
from drawing_checker.core.models import PackageContent, Severity
from drawing_checker.drawing.dimensions import extract_dimensions
from drawing_checker.drawing.pdfdoc import DrawingPdf

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def make_ctx(tmp_path: Path, lines, profile="default") -> CheckContext:
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    kwargs = {}
    if Path(FONT).exists():
        page.insert_font(fontname="T", fontfile=FONT)
        kwargs["fontname"] = "T"
    for i, line in enumerate(list(lines) + ["Testzeichnung Blatt 1 von 1"]):
        page.insert_text((40, 60 + i * 30), line, fontsize=10, **kwargs)
    path = tmp_path / "t.pdf"
    doc.save(path)
    doc.close()
    return CheckContext("123", DrawingPdf(path), PackageContent(),
                        load_profile(profile))


def codes(ctx) -> dict:
    run_process_checks(ctx, extract_dimensions(ctx.pdf))
    return {f.code: f for f in ctx.findings}


# ------------------------------------------------------------- Schweißen
def test_weld_without_size_is_error(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff S355J2",
                                  "Kehlnaht umlaufend, ISO 5817-C"]))
    assert c["WELD.NO_SIZE"].severity == Severity.ERROR


def test_weld_with_a_size_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff S355J2",
                                  "Kehlnaht a4 umlaufend, ISO 5817-C"]))
    assert "WELD.NO_SIZE" not in c


def test_weld_with_z_size_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff S355J2",
                                  "Kehlnaht z6 umlaufend"]))
    assert "WELD.NO_SIZE" not in c


def test_mixed_a_and_z_sizes_warn(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff S355J2",
                                  "Naht 1: a4 umlaufend",
                                  "Naht 2: z6 beidseitig"]))
    assert c["WELD.AZ_MIXED"].severity == Severity.WARNING
    assert "29" in c["WELD.AZ_MIXED"].detail


def test_butt_weld_without_preparation_warns(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff S355J2",
                                  "V-Naht durchgeschweißt a6, ISO 5817-B"]))
    assert c["WELD.NO_PREP"].severity == Severity.WARNING


def test_butt_weld_with_preparation_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, [
        "Werkstoff S355J2", "V-Naht a6, Nahtvorbereitung nach ISO 9692-1",
        "Öffnungswinkel 60°, Wurzelspalt 2 mm"]))
    assert "WELD.NO_PREP" not in c


def test_no_weld_context_no_findings(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff C45", "gedrehtes Teil"]))
    assert not [k for k in c if k.startswith("WELD.")]


# ------------------------------------------------------------------ Guss
def test_casting_without_draft_warns(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff EN-GJS-400-15",
                                  "Gussteil nach ISO 8062-3 DCTG12"]))
    assert c["CAST.NO_DRAFT"].severity == Severity.WARNING


def test_casting_with_draft_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff EN-GJS-400-15", "Gussteil",
                                  "Formschrägen 2° wenn nicht anders angegeben",
                                  "Bearbeitungszugabe 3 mm"]))
    assert "CAST.NO_DRAFT" not in c
    assert "CAST.NO_RMA" not in c


def test_machined_casting_without_rma_warns(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff EN-GJL-250", "Gussteil",
                                  "Formschrägen 2°",
                                  "Passflächen bearbeitet, Ra 3,2"]))
    assert c["CAST.NO_RMA"].severity == Severity.WARNING


def test_unmachined_casting_needs_no_rma(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff EN-GJL-250",
                                  "Gussteil roh, Formschrägen 3°"]))
    assert "CAST.NO_RMA" not in c


# ----------------------------------------------------------------- Blech
def test_sheet_without_thickness_is_error(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff S235JR",
                                  "Blech lasergeschnitten, abgekantet"]))
    assert c["SHEET.NO_THICK"].severity == Severity.ERROR


def test_sheet_with_thickness_is_fine(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff S235JR",
                                  "Blechdicke 3 mm, abgekantet",
                                  "Biegeradius innen R3"]))
    assert "SHEET.NO_THICK" not in c
    assert "SHEET.NO_RADIUS" not in c


def test_bending_without_radius_warns(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff S235JR", "Blechdicke 2 mm",
                                  "abgekantet 90°"]))
    assert c["SHEET.NO_RADIUS"].severity == Severity.WARNING


def test_flat_sheet_needs_no_radius(tmp_path):
    c = codes(make_ctx(tmp_path, ["Werkstoff S235JR", "Blechdicke 2 mm",
                                  "Blech lasergeschnitten, eben"]))
    assert "SHEET.NO_RADIUS" not in c


def test_turned_part_no_process_findings(tmp_path):
    """Ein Drehteil darf keine Schweiß-, Guss- oder Blechregel auslösen."""
    c = codes(make_ctx(tmp_path, [
        "Werkstoff 42CrMo4 +QT", "Antriebswelle, gedreht und geschliffen",
        "⌀40 k6, Ra 0,8, Allgemeintoleranzen ISO 2768-fH"]))
    assert not c, f"unerwartete Findings: {list(c)}"
