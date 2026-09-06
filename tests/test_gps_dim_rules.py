"""GPS-Tiefenprüfung, Bemaßungs- und Fertigungsregeln.

Der Helfer platziert Texte an exakten Koordinaten, weil die Maßketten-
Erkennung bewusst die räumliche Anordnung auswertet.
"""
from pathlib import Path

import pymupdf
import pytest

from drawing_checker.checks.base import CheckContext, load_profile
from drawing_checker.checks.dimension_checks import run_dimension_checks
from drawing_checker.checks.gps_checks import run_gps_checks
from drawing_checker.core.models import PackageContent, Severity
from drawing_checker.drawing.dimensions import extract_dimensions
from drawing_checker.drawing.pdfdoc import DrawingPdf

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def make_ctx(tmp_path: Path, items, profile="default") -> CheckContext:
    """items: Text (untereinander) oder (x, y, text) für exakte Position."""
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    kwargs = {}
    if Path(FONT).exists():
        page.insert_font(fontname="T", fontfile=FONT)
        kwargs["fontname"] = "T"
    y = 60
    for item in list(items) + ["Interne Testzeichnung Blatt 1"]:
        if isinstance(item, tuple):
            x, yy, text = item
        else:
            x, yy, text = 40, y, item
            y += 30
        page.insert_text((x, yy), text, fontsize=10, **kwargs)
    path = tmp_path / "t.pdf"
    doc.save(path)
    doc.close()
    return CheckContext("123", DrawingPdf(path), PackageContent(),
                        load_profile(profile))


class _FakeBlock:
    """Textblock-Stub mit Dummy-Position."""

    def __init__(self, text, i=0):
        from drawing_checker.core.models import BBox
        self.text = text
        self.bbox = BBox(10, 10 + i * 20, 200, 25 + i * 20)
        self.page = 0


class _FakePdf:
    """PDF-Stub für symbolbasierte Tests.

    DejaVu (die Testschrift) kann ⌖/Ⓜ/Ⓔ nicht darstellen; echte CAD-PDFs
    schon. Der Stub liefert den Text direkt, damit die Symbolregeln
    unabhängig von der Schriftabdeckung geprüft werden können.
    """

    def __init__(self, lines):
        self._blocks = [_FakeBlock(t, i) for i, t in enumerate(lines)]

    def blocks(self):
        return self._blocks

    def full_text(self):
        return "\n".join(b.text for b in self._blocks)

    def words(self):
        from drawing_checker.core.models import BBox
        from drawing_checker.drawing.pdfdoc import Word
        out = []
        for b in self._blocks:
            for i, t in enumerate(b.text.split()):
                out.append(Word(t, BBox(b.bbox.x0 + i * 20, b.bbox.y0,
                                        b.bbox.x0 + i * 20 + 15, b.bbox.y1),
                                0))
        return out


def sym_ctx(lines, profile="default") -> CheckContext:
    return CheckContext("123", _FakePdf(lines), PackageContent(),
                        load_profile(profile))


def run_all(ctx) -> dict:
    dims = extract_dimensions(ctx.pdf)
    run_gps_checks(ctx, dims)
    run_dimension_checks(ctx, dims)
    return {f.code: f for f in ctx.findings}


# =========================================================== GPS-Regeln
def test_fit_without_envelope_warns():
    """Klassiker: ⌀20 H7 ohne Ⓔ – Form bleibt nach ISO 8015 unbegrenzt."""
    c = run_all(sym_ctx(["Werkstoff C45", "Lagersitz ⌀20 H7",
                         "Tolerierung ISO 8015"]))
    assert c["GPS.ENVELOPE"].severity == Severity.WARNING
    assert "H7" in c["GPS.ENVELOPE"].text


def test_fit_with_envelope_symbol_is_fine():
    c = run_all(sym_ctx(["Werkstoff C45", "⌀20 H7 Ⓔ"]))
    assert "GPS.ENVELOPE" not in c


def test_fit_with_form_tolerance_is_fine():
    c = run_all(sym_ctx(["Werkstoff C45", "⌀20 H7", "⌭ 0,01"]))
    assert "GPS.ENVELOPE" not in c


def test_coarse_fit_not_flagged():
    """Grobe Passungen (IT ≥ 9) sind unkritisch."""
    c = run_all(sym_ctx(["Werkstoff C45", "⌀22 H11"]))
    assert "GPS.ENVELOPE" not in c


def test_undefined_datum_is_error():
    c = run_all(sym_ctx(["Werkstoff C45", "⌖ ⌀0,2 X"]))
    assert c["GPS.DATUM_UNDEFINED"].severity == Severity.ERROR
    assert "X" in c["GPS.DATUM_UNDEFINED"].text


def test_defined_datum_is_fine():
    c = run_all(sym_ctx(["Werkstoff C45", "⌖ ⌀0,2 A",
                         "Bezug A = Auflagefläche"]))
    assert "GPS.DATUM_UNDEFINED" not in c


def test_position_without_ted_warns():
    c = run_all(sym_ctx(["Werkstoff C45", "⌖ ⌀0,2 A",
                         "Bezug A", "Abstand 50±0,1"]))
    assert c["GPS.POSITION_NO_TED"].severity == Severity.WARNING


def test_position_with_ted_is_fine():
    c = run_all(sym_ctx(["Werkstoff C45", "⌖ ⌀0,2 A",
                         "Bezug A", "[50]", "[30]"]))
    assert "GPS.POSITION_NO_TED" not in c


def test_modifier_on_form_tolerance_is_error():
    c = run_all(sym_ctx(["Werkstoff C45", "⏥ 0,05 Ⓜ"]))
    assert c["GPS.MOD_ON_FORM"].severity == Severity.ERROR


# ====================================================== Maßketten-Check
def test_closed_chain_detected(tmp_path):
    """Echte horizontale Kette: 20+30+50 = 100, Teil und Summe toleriert."""
    items = [
        (40, 300, "20±0,1"), (140, 300, "30±0,1"), (240, 300, "50±0,1"),
        (140, 340, "100±0,1"),
        (40, 60, "Werkstoff C45"),
    ]
    c = run_all(make_ctx(tmp_path, items))
    assert c["DIM.CHAIN"].severity == Severity.WARNING
    assert "Maßkette" in c["DIM.CHAIN"].text


def test_open_chain_is_fine(tmp_path):
    """Nur das Gesamtmaß toleriert = korrekte offene Kette."""
    items = [
        (40, 300, "20"), (140, 300, "30"), (240, 300, "50"),
        (140, 340, "100±0,1"),
        (40, 60, "Werkstoff C45"),
    ]
    c = run_all(make_ctx(tmp_path, items))
    assert "DIM.CHAIN" not in c


def test_scattered_dimensions_no_false_chain(tmp_path):
    """Zufällig passende Summen ohne gemeinsame Maßlinie -> kein Finding."""
    items = [
        (40, 100, "20±0,1"), (400, 250, "30±0,1"), (700, 480, "50±0,1"),
        (100, 520, "100±0,1"),
        (40, 60, "Werkstoff C45"),
    ]
    c = run_all(make_ctx(tmp_path, items))
    assert "DIM.CHAIN" not in c


# ================================================ Fertigungsgerechtigkeit
def test_tight_tolerance_flagged(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "Lagersitz ⌀30 h4",
                                    "Länge 80±0,003"]))
    assert c["MFG.TIGHT_TOL"].severity == Severity.WARNING


def test_normal_tolerance_not_flagged(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "⌀30 h9", "80±0,2"]))
    assert "MFG.TIGHT_TOL" not in c


def test_deep_hole_flagged(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "⌀8 ↧80"]))
    assert c["MFG.DEEP_HOLE"].severity == Severity.WARNING
    assert "10.0:1" in c["MFG.DEEP_HOLE"].text


def test_shallow_hole_not_flagged(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "⌀20 ↧40"]))
    assert "MFG.DEEP_HOLE" not in c


def test_sharp_corner_flagged(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "Innenecken R0"]))
    assert c["MFG.SHARP_CORNER"].severity == Severity.WARNING


def test_normal_radius_not_flagged(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "Innenecken R3"]))
    assert "MFG.SHARP_CORNER" not in c


# ============================================== Oberflächen-Plausibilität
def test_fine_ra_on_cast_surface_is_error(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff EN-GJL-250",
                                    "Gussteil, Oberfläche Ra 0,8"]))
    assert c["SURF.UNREALISTIC"].severity == Severity.ERROR


def test_fine_ra_with_grinding_is_fine(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff 42CrMo4",
                                    "Lagersitze geschliffen, Ra 0,2"]))
    assert "SURF.UNREALISTIC" not in c


def test_very_fine_ra_without_process_warns(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff 42CrMo4", "Ra 0,1"]))
    assert c["SURF.UNREALISTIC"].severity == Severity.WARNING


def test_normal_ra_is_fine(tmp_path):
    c = run_all(make_ctx(tmp_path, ["Werkstoff 42CrMo4", "Ra 3,2"]))
    assert "SURF.UNREALISTIC" not in c


# ================================================== Regressionsschutz
def test_clean_drawing_triggers_no_new_rules(tmp_path):
    """Eine saubere Zeichnung darf keine der neuen Regeln auslösen."""
    c = run_all(make_ctx(tmp_path, [
        "Werkstoff 42CrMo4 +QT",
        "Allgemeintoleranzen ISO 2768-fH, Tolerierung ISO 8015",
        "⌀40 h6 (E), ⌀55 h6 (E)",
        "Oberfläche Ra 1,6, Lagersitze geschliffen Ra 0,8",
        "Kanten ISO 13715, Innenradien R3",
    ]))
    new_codes = {k for k in c
                 if k.startswith(("GPS.", "DIM.", "MFG.", "SURF.UNREAL"))}
    assert not new_codes, f"unerwartete Findings: {new_codes}"
