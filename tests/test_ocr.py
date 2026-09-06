"""Tests des OCR-Pfads.

Die reinen Rechenteile (Nachkorrektur, Rückrechnung gedrehter Fundstellen,
Binarisierung, Schräglagenschätzung, Einstellungen) laufen immer. Die
Erkennung selbst braucht Tesseract und wird sonst übersprungen – auf
Rechnern ohne OCR fällt der Checker dokumentiert zurück.
"""
from __future__ import annotations

import io

import pymupdf
import pytest

from drawing_checker.core.models import BBox
from drawing_checker.drawing import ocr as ocrmod
from drawing_checker.drawing.ocr import OcrSettings, _fix_token, _unrotate
from drawing_checker.drawing.pdfdoc import DrawingPdf, Word

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
has_tesseract = ocrmod._tesseract() is not None
needs_ocr = pytest.mark.skipif(not has_tesseract,
                               reason="Tesseract nicht installiert")


# ------------------------------------------------------------ Nachkorrektur
@pytest.mark.parametrize("raw,erwartet", [
    ("1O0", "100"),          # Buchstabe O in reiner Zahl
    ("|2", "2"),             # Strichrest vor der Zahl
    ("Ø20", "⌀20"),          # Durchmesser-Variante vereinheitlichen
    ("@20", "⌀20"),          # Durchmesserzeichen als @ erkannt
    ("S235JR", "S235JR"),    # Werkstoff bleibt unangetastet
    ("[50]", "[50]"),        # theoretisch genaues Maß behält die Klammern
    ("M12x1,5", "M12x1,5"),
    ("1.4301", "1.4301"),
])
def test_fix_token(raw, erwartet):
    assert _fix_token(raw) == erwartet


def test_fix_token_laesst_buchstaben_in_gemischten_token(): 
    """In "R10x2" darf kein O/0-Tausch passieren – es ist keine reine Zahl."""
    assert _fix_token("R1Ox2") == "R1Ox2"


# ------------------------------------------------- gedrehte Fundstellen
def test_unrotate_90_grad():
    """Ein Kasten oben links im gedrehten Bild liegt unten links im Original."""
    # Originalhöhe 100; im 90°-Bild liegt (x=10, y=20, w=30, h=5)
    x, y, w, h = _unrotate(10, 20, 30, 5, 90, orig_height=100)
    assert (x, y, w, h) == (20, 100 - 10 - 30, 5, 30)


def test_unrotate_laesst_unbekannte_winkel():
    assert _unrotate(1, 2, 3, 4, 45, 100) == (1, 2, 3, 4)


def test_dedupe_entfernt_doppelfunde():
    a = Word("⌀20", BBox(0, 0, 10, 5), 0, 90)
    b = Word("20", BBox(1, 0, 10, 5), 0, 95)      # gleiche Stelle, kürzer
    kept = ocrmod._dedupe([a, b])
    assert [w.text for w in kept] == ["⌀20"]


def test_dedupe_behaelt_getrennte_funde():
    a = Word("20", BBox(0, 0, 10, 5), 0, 90)
    b = Word("30", BBox(50, 0, 60, 5), 0, 90)
    assert len(ocrmod._dedupe([a, b])) == 2


# ------------------------------------------------------------ Einstellungen
def test_settings_aus_umgebung(monkeypatch):
    monkeypatch.setenv("DRAWING_CHECKER_OCR_DPI", "250")
    monkeypatch.setenv("DRAWING_CHECKER_OCR_PSM", "6")
    monkeypatch.setenv("DRAWING_CHECKER_OCR_ROTATIONS", "90,270")
    monkeypatch.setenv("DRAWING_CHECKER_OCR_BINARIZE", "0")
    cfg = OcrSettings.from_env()
    assert (cfg.dpi, cfg.psm, cfg.rotations, cfg.binarize) == (
        250, 6, (90, 270), False)


def test_settings_config_schaltet_woerterbuecher_ab():
    cfg = OcrSettings()
    config = cfg.config()
    assert "--psm 11" in config and "load_system_dawg=0" in config


def test_settings_ignoriert_unsinn(monkeypatch):
    monkeypatch.setenv("DRAWING_CHECKER_OCR_DPI", "keine Zahl")
    assert OcrSettings.from_env().dpi == OcrSettings().dpi


# ----------------------------------------------------------- Bildaufbau
def test_binarize_erzeugt_zwei_werte():
    from PIL import Image
    import numpy as np

    arr = np.tile(np.arange(256, dtype="uint8"), (16, 1))
    out = ocrmod._binarize(Image.fromarray(arr), Image)
    assert set(np.unique(np.asarray(out))) <= {0, 255}


def test_skew_angle_erkennt_schraege():
    from PIL import Image
    import numpy as np

    # Waagerechte Textzeilen, um 2° verdreht -> Schätzer muss gegensteuern.
    arr = np.full((400, 400), 255, dtype="uint8")
    for row in range(40, 360, 40):
        arr[row:row + 6, 40:360] = 0
    img = Image.fromarray(arr).rotate(-2.0, fillcolor=255)
    angle = ocrmod._skew_angle(img, OcrSettings())
    assert 1.0 <= angle <= 3.0


def test_skew_angle_bei_gerader_vorlage_null():
    from PIL import Image
    import numpy as np

    arr = np.full((400, 400), 255, dtype="uint8")
    for row in range(40, 360, 40):
        arr[row:row + 6, 40:360] = 0
    assert ocrmod._skew_angle(Image.fromarray(arr), OcrSettings()) == 0.0


# ------------------------------------------------------------- Erkennung
def _scan_pdf(tmp_path, lines, rotated: list[str] | None = None,
              dpi: int = 200):
    """Baut ein Text-PDF, rastert es und liefert den Scan-Pfad."""
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    kwargs = {}
    from pathlib import Path

    if Path(FONT).exists():
        page.insert_font(fontname="T", fontfile=FONT)
        kwargs["fontname"] = "T"
    for i, text in enumerate(lines):
        page.insert_text((60, 80 + i * 40), text, fontsize=16, **kwargs)
    for i, text in enumerate(rotated or []):
        # 90° gedreht, wie Maßtexte an senkrechten Maßlinien
        page.insert_text((600 + i * 40, 400), text, fontsize=16,
                         rotate=90, **kwargs)
    src = tmp_path / "text.pdf"
    doc.save(src)
    doc.close()

    scan = tmp_path / "scan.pdf"
    from tools.ocr_bench import rasterize

    rasterize(src, scan, dpi=dpi, noise=False)
    return scan


@needs_ocr
def test_ocr_liest_gescannte_zeichnung(tmp_path):
    scan = _scan_pdf(tmp_path, ["Werkstoff S235JR", "Gewicht 12,5 kg",
                                "Allgemeintoleranz ISO 2768-mK"])
    with DrawingPdf(scan) as pdf:
        text = pdf.full_text()
        assert pdf.ocr_used
        assert "S235JR" in text.replace(" ", "")
        assert "2768" in text


@needs_ocr
def test_ocr_findet_gedrehte_masstexte(tmp_path):
    scan = _scan_pdf(tmp_path, ["Ansicht A"], rotated=["148,5", "96,0"])
    with DrawingPdf(scan) as pdf:
        text = pdf.full_text().replace(" ", "")
    assert "148" in text, "gedrehter Maßtext wurde nicht gefunden"


@needs_ocr
def test_ocr_wortkonfidenz_wird_uebernommen(tmp_path):
    scan = _scan_pdf(tmp_path, ["Werkstoff S235JR", "Gewicht 12,5 kg"])
    with DrawingPdf(scan) as pdf:
        confs = [w.conf for w in pdf.words()]
    assert confs and all(0 <= c <= 100 for c in confs)
    assert max(confs) < 100.0, "OCR-Wörter dürfen nicht als sicher gelten"


@needs_ocr
def test_gemischtes_dokument_nutzt_beide_wege(tmp_path):
    """Seite 1 mit Textlayer, Seite 2 als Scan – beides muss ankommen."""
    doc = pymupdf.open()
    p1 = doc.new_page(width=842, height=595)
    p1.insert_text((60, 80), "Blatt 1 Werkstoff 1.4301 Allgemeintoleranz",
                   fontsize=14)
    src = tmp_path / "seite2.pdf"
    d2 = pymupdf.open()
    d2.new_page(width=842, height=595).insert_text(
        (60, 80), "Blatt 2 Schweissnaht a4 umlaufend", fontsize=16)
    d2.save(src)
    d2.close()
    from tools.ocr_bench import rasterize

    scan2 = rasterize(src, tmp_path / "scan2.pdf", dpi=200, noise=False)
    doc.insert_pdf(pymupdf.open(scan2))
    path = tmp_path / "gemischt.pdf"
    doc.save(path)
    doc.close()

    with DrawingPdf(path) as pdf:
        text = pdf.full_text()
        assert pdf.ocr_used, "Scan-Seite wurde nicht per OCR nachgezogen"
        assert "1.4301" in text, "Textlayer der ersten Seite fehlt"
        assert "umlaufend" in text.lower(), "Scan-Seite wurde nicht gelesen"


@needs_ocr
def test_unsichere_kurze_zahlen_werden_kein_mass(tmp_path):
    """Kurze OCR-Schnipsel unter der Konfidenzschwelle sind keine Maße."""
    from drawing_checker.drawing.dimensions import extract_dimensions

    scan = _scan_pdf(tmp_path, ["Laenge 120", "Breite 80"])
    with DrawingPdf(scan) as pdf:
        for w in pdf.words():
            w.conf = 30.0
        assert extract_dimensions(pdf, 6000) == []


# ------------------------------------------------ Härtegrad bei OCR-Text
def test_findings_werden_bei_ocr_herabgestuft(tmp_path):
    """Auf OCR-Grundlage darf keine Regel hart als Fehler melden."""
    from drawing_checker.checks.base import CheckContext, load_profile
    from drawing_checker.core.models import PackageContent, Severity

    class _PdfStub:
        ocr_used = True

    ctx = CheckContext("1", _PdfStub(), PackageContent(),
                       load_profile("default"))
    ctx.add("TB.MATERIAL", "Werkstoff nicht nachweisbar")
    assert ctx.findings[0].severity == Severity.WARNING
    assert "Herabgestuft" in ctx.findings[0].detail


def test_paketfehler_bleibt_hart_trotz_ocr():
    from drawing_checker.checks.base import CheckContext, load_profile
    from drawing_checker.core.models import PackageContent, Severity

    class _PdfStub:
        ocr_used = True

    ctx = CheckContext("1", _PdfStub(), PackageContent(),
                       load_profile("default"))
    ctx.add("DOC.NO_PDF", "Kein PDF im Paket")
    assert ctx.findings[0].severity == Severity.BLOCKER


def test_ohne_ocr_bleibt_die_severity(tmp_path):
    from drawing_checker.checks.base import CheckContext, load_profile
    from drawing_checker.core.models import PackageContent, Severity

    class _PdfStub:
        ocr_used = False

    ctx = CheckContext("1", _PdfStub(), PackageContent(),
                       load_profile("default"))
    ctx.add("TB.MATERIAL", "Werkstoff nicht nachweisbar")
    assert ctx.findings[0].severity == Severity.ERROR
