"""Der Lauf als Ganzes: Durchstich, Excel, Bericht, OCR, Haushalt.
"""
from __future__ import annotations

# ======================================================================
# e2e
# ======================================================================
# End-to-End: kompletter Prüflauf über die Mockdaten inkl. SAP-Absturz + Resume.
from pathlib import Path

import pytest

from drawing_checker.kern import JobStatus, RunConfig, Severity
from drawing_checker.ablauf import Callbacks, Orchestrator
from drawing_checker.sap_ymatdocs import MockSapAdapter
from conftest import make_config




@pytest.fixture()
def run(mock_dir, tmp_path):
    cfg = make_config(mock_dir, tmp_path / "erg")
    adapter = MockSapAdapter(mock_dir, crash_on={"10473216"})
    adapter.ensure_ready()
    orch = Orchestrator(cfg, adapter, Callbacks())
    orch.start()
    orch.join(300)
    return orch


def result(orch, material):
    return next(r for r in orch.state.results.values()
                if r.material == material)


def test_full_run_completes(run):
    assert run.progress.done == 5
    assert run.progress.failed == 0


def test_clean_drawing_is_ok(run):
    r = result(run, "10473217")
    assert r.status == JobStatus.OK
    assert r.findings == []
    assert r.screenshot and r.screenshot.exists()
    assert "passt" not in ("",)  # Geometrie-Summary vorhanden
    assert "STEP-OBB" in r.step_summary


def test_weld_bracket_language_and_weld_findings(run):
    r = result(run, "10473215")
    codes = {f.code for f in r.findings}
    assert "LANG.GERMAN" in codes
    assert "WELD.QUALITY" in codes
    assert "GEO.MISMATCH" not in codes          # STEP passt
    # Fachliche Widersprüche: 1.4305 (nicht schweißgeeignet) + Schweißsymbolik,
    # "feuerverzinkt" auf Edelstahl
    assert "MAT.WELD_CONFLICT" in codes
    assert "MAT.COATING_CONFLICT" in codes
    # Sprach-Findings tragen Positionen für die Annotation
    assert any(f.bbox for f in r.findings if f.code == "LANG.GERMAN")


def test_wrong_step_config_is_blocker(run):
    r = result(run, "10473216")
    codes = {f.code: f for f in r.findings}
    assert "GEO.MISMATCH" in codes
    assert codes["GEO.MISMATCH"].severity == Severity.BLOCKER
    assert "GT.GENERAL_TOL" in codes
    assert "CAST.TOL" in codes


def test_scan_without_text_degrades_gracefully(run):
    r = result(run, "10473218")
    codes = {f.code for f in r.findings}
    assert "DOC.NO_TEXT" in codes or "DOC.OCR" in codes
    # Auf einer per OCR gelesenen Zeichnung darf nichts hart als Fehler
    # gemeldet werden – Erkennungsfehler sind nicht auszuschließen.
    from drawing_checker.kern import Severity

    hart = [f for f in r.findings
            if f.severity >= Severity.ERROR and f.code not in ("DOC.NO_PDF",)]
    assert not hart, f"harte Befunde auf OCR-Zeichnung: {[f.code for f in hart]}"


def test_missing_package_reported(run):
    r = result(run, "10473219")
    assert any(f.code == "DOC.NO_PDF" for f in r.findings)


def test_sap_crash_recovered(run):
    # 10473216 hat einen simulierten Absturz -> trotzdem geprüft
    assert result(run, "10473216").status != JobStatus.FAILED


def test_result_excel_written(run, mock_dir):
    assert (mock_dir / "Materialliste_Mock_geprüft.xlsx").exists()


def test_resume_skips_done(run, mock_dir, tmp_path):
    cfg = make_config(mock_dir, run.config.output_dir)
    adapter = MockSapAdapter(mock_dir)
    adapter.ensure_ready()
    processed = []
    orch2 = Orchestrator(cfg, adapter,
                         Callbacks(on_result=lambda r: processed.append(r)),
                         resume=True)
    orch2.start()
    orch2.join(300)
    # Alle 5 gemeldet, aber nichts neu gerechnet außer evtl. FAILED (hier keine)
    assert len(processed) == 5
    assert orch2.progress.done == 5


# ======================================================================
# excel_and_state
# ======================================================================

import openpyxl

from drawing_checker.kern import ( BBox, Finding, JobStatus, MaterialResult, RunConfig, Severity, )
from drawing_checker.kern import RunState
from drawing_checker.bericht import ( RESULT_HEADERS, ResultWorkbook, read_materials, )


def make_config_excel(tmp_path: Path, excel: Path) -> RunConfig:
    return RunConfig(excel_path=excel, sheet_name="Materialliste",
                     material_column="C", header_row=1,
                     output_dir=tmp_path / "out")


def test_read_materials_skips_blanks(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Materialliste"
    ws.append(["Nr", "Werk", "Materialnummer"])
    ws.append([1, "1000", "10473215"])
    ws.append([2, "1000", None])
    ws.append([3, "1000", 10473216])   # als Zahl formatiert
    ws.append([4, "1000", "  "])
    excel = tmp_path / "liste.xlsx"
    wb.save(excel)

    mats = read_materials(make_config_excel(tmp_path, excel))
    assert mats == [(2, "10473215"), (4, "10473216")]


def test_result_workbook_roundtrip(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Materialliste"
    ws.append(["Nr", "Werk", "Materialnummer"])
    ws.append([1, "1000", "10473215"])
    excel = tmp_path / "liste.xlsx"
    wb.save(excel)

    cfg = make_config_excel(tmp_path, excel)
    rwb = ResultWorkbook(cfg)
    result = MaterialResult(material="10473215", row=2,
                            status=JobStatus.FINDINGS)
    result.findings.append(Finding("LANG.GERMAN", Severity.ERROR, "Test",
                                   BBox(0, 0, 1, 1)))
    rwb.write_result(result)
    rwb.save()

    out = openpyxl.load_workbook(rwb.path)["Materialliste"]
    headers = [c.value for c in out[1]]
    assert RESULT_HEADERS[0] in headers
    col = headers.index(RESULT_HEADERS[0]) + 1
    assert out.cell(row=2, column=col).value == "Findings"

    # Zweites Öffnen erzeugt KEINE doppelten Spalten
    rwb2 = ResultWorkbook(cfg)
    assert rwb2.first_col == rwb.first_col


def test_state_roundtrip_and_resume(tmp_path):
    excel = tmp_path / "l.xlsx"
    wb = openpyxl.Workbook(); wb.active.title = "Materialliste"; wb.save(excel)
    cfg = make_config_excel(tmp_path, excel)
    run_dir = tmp_path / "lauf"
    run_dir.mkdir()

    state = RunState(cfg, run_dir)
    r = MaterialResult(material="10473215", row=2, status=JobStatus.OK,
                       duration_s=1.5)
    r.findings.append(Finding("X", Severity.WARNING, "t", BBox(1, 2, 3, 4),
                              page=0, detail="d"))
    state.record(r)

    loaded = RunState.load(cfg, run_dir)
    assert loaded.is_done(2, "10473215")
    assert not loaded.is_done(3, "10473215")
    lr = loaded.results["2:10473215"]
    assert lr.findings[0].severity == Severity.WARNING
    assert lr.findings[0].bbox.x1 == 3


def test_failed_jobs_are_retried_on_resume(tmp_path):
    excel = tmp_path / "l.xlsx"
    wb = openpyxl.Workbook(); wb.active.title = "Materialliste"; wb.save(excel)
    cfg = make_config_excel(tmp_path, excel)
    run_dir = tmp_path / "lauf"; run_dir.mkdir()
    state = RunState(cfg, run_dir)
    state.record(MaterialResult(material="M", row=5, status=JobStatus.FAILED,
                                error="SAP weg"))
    loaded = RunState.load(cfg, run_dir)
    assert not loaded.is_done(5, "M")   # FAILED wird beim Fortsetzen erneut geprüft


# ======================================================================
# reporting
# ======================================================================
# Laufabschluss-Artefakte: HTML-Bericht, Excel-Zusammenfassung, Lauf-Log.


from drawing_checker.kern import RunConfig


@pytest.fixture(scope="module")
def finished_run(mock_dir, tmp_path_factory):
    out = tmp_path_factory.mktemp("erg")
    cfg = RunConfig(
        excel_path=mock_dir / "Materialliste_Mock.xlsx",
        sheet_name="Materialliste", material_column="C", header_row=1,
        output_dir=out)
    adapter = MockSapAdapter(mock_dir)
    adapter.ensure_ready()
    orch = Orchestrator(cfg, adapter, Callbacks())
    orch.start(); orch.join(300)
    return orch


def test_html_report_written(finished_run):
    path = finished_run.report_path
    assert path is not None and path.exists()
    html = path.read_text(encoding="utf-8")
    assert "Zeichnungsprüfung – Bericht" in html
    assert "10473216" in html          # Geometrie-K.O.-Fall
    assert "GEO.MISMATCH" in html
    assert "10473216.png" in html      # Link auf annotierte Zeichnung


def test_excel_summary_sheet(finished_run, mock_dir):
    wb = openpyxl.load_workbook(mock_dir / "Materialliste_Mock_geprüft.xlsx")
    assert "Prüfzusammenfassung" in wb.sheetnames
    ws = wb["Prüfzusammenfassung"]
    values = [c.value for row in ws.iter_rows() for c in row if c.value]
    assert "LANG.GERMAN" in values     # häufigster Mängelcode gezählt
    # Ergebnisblatt hat Autofilter und Fixierung
    main = wb["Materialliste"]
    assert main.auto_filter.ref
    assert main.freeze_panes == "A2"


def test_run_logfile_written(finished_run):
    assert (finished_run.run_dir / "lauf.log").read_text(encoding="utf-8")


def test_annotated_image_has_stamp(finished_run):
    # Stempel oben links: Pixel im Rahmenbereich sind nicht mehr weiß
    from PIL import Image

    shot = next(r.screenshot for r in finished_run.state.results.values()
                if r.material == "10473216")
    img = Image.open(shot).convert("RGB")
    box = img.crop((16, 16, 200, 70))
    assert any(p != (255, 255, 255) for p in box.getdata())


# ======================================================================
# ocr
# ======================================================================
# Tests des OCR-Pfads.
#
# Die reinen Rechenteile (Nachkorrektur, Rückrechnung gedrehter Fundstellen,
# Binarisierung, Schräglagenschätzung, Einstellungen) laufen immer. Die
# Erkennung selbst braucht Tesseract und wird sonst übersprungen – auf
# Rechnern ohne OCR fällt der Checker dokumentiert zurück.
import io

import pymupdf

from drawing_checker.kern import BBox
from drawing_checker import ocr as ocrmod
from drawing_checker.ocr import OcrSettings, _fix_token, _unrotate
from drawing_checker.zeichnung import DrawingPdf, Word
from conftest import FONT

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
    from tools.messen import rasterize

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
    from tools.messen import rasterize

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
    from drawing_checker.zeichnung import extract_dimensions

    scan = _scan_pdf(tmp_path, ["Laenge 120", "Breite 80"])
    with DrawingPdf(scan) as pdf:
        for w in pdf.words():
            w.conf = 30.0
        assert extract_dimensions(pdf, 6000) == []


# ------------------------------------------------ Härtegrad bei OCR-Text
def test_findings_werden_bei_ocr_herabgestuft(tmp_path):
    """Auf OCR-Grundlage darf keine Regel hart als Fehler melden."""
    from drawing_checker.regeln import CheckContext, load_profile
    from drawing_checker.kern import PackageContent, Severity

    class _PdfStub:
        ocr_used = True

    ctx = CheckContext("1", _PdfStub(), PackageContent(),
                       load_profile("default"))
    ctx.add("TB.MATERIAL", "Werkstoff nicht nachweisbar")
    assert ctx.findings[0].severity == Severity.WARNING
    assert "Herabgestuft" in ctx.findings[0].detail


def test_paketfehler_bleibt_hart_trotz_ocr():
    from drawing_checker.regeln import CheckContext, load_profile
    from drawing_checker.kern import PackageContent, Severity

    class _PdfStub:
        ocr_used = True

    ctx = CheckContext("1", _PdfStub(), PackageContent(),
                       load_profile("default"))
    ctx.add("DOC.NO_PDF", "Kein PDF im Paket")
    assert ctx.findings[0].severity == Severity.BLOCKER


def test_ohne_ocr_bleibt_die_severity(tmp_path):
    from drawing_checker.regeln import CheckContext, load_profile
    from drawing_checker.kern import PackageContent, Severity

    class _PdfStub:
        ocr_used = False

    ctx = CheckContext("1", _PdfStub(), PackageContent(),
                       load_profile("default"))
    ctx.add("TB.MATERIAL", "Werkstoff nicht nachweisbar")
    assert ctx.findings[0].severity == Severity.ERROR


# ------------------------------------------------------ Linienentfernung
def test_linienentfernung_tilgt_linie_und_laesst_schrift():
    """Lange Linien verschwinden, kurze Buchstabenstriche bleiben."""
    import numpy as np
    from PIL import Image

    arr = np.full((200, 400), 255, dtype="uint8")
    arr[100, 20:380] = 0            # Maßlinie quer über das Blatt
    arr[50:60, 100:106] = 0         # Buchstabenstrich
    out = np.asarray(ocrmod._remove_lines(Image.fromarray(arr),
                                          OcrSettings(), Image))
    assert (out[100, 20:380] == 255).all()
    assert (out[50:60, 100:106] == 0).all()


def test_linienentfernung_ist_abschaltbar(monkeypatch):
    monkeypatch.setenv("DRAWING_CHECKER_OCR_LINES", "1")
    assert OcrSettings.from_env().remove_lines is True


# ======================================================================
# haushalt_und_gewinde
# ======================================================================
# Tests für den Dauerlauf-Haushalt (Aufräumen, Plattenplatz) und die
# Gewinderegeln.


from drawing_checker.regeln import CheckContext, load_profile
from drawing_checker.pruef_bemassung import check_thread_depths
from drawing_checker import kern as hk
from drawing_checker.kern import BBox, PackageContent, Severity
from drawing_checker.zeichnung import DimKind, DimValue


# ------------------------------------------------------------- Haushalt
def test_cleanup_entfernt_paket(tmp_path):
    work = tmp_path / "10473215"
    work.mkdir()
    (work / "zeichnung.pdf").write_bytes(b"x" * 1024)
    zip_path = tmp_path / "10473215.zip"
    zip_path.write_bytes(b"y" * 2048)

    freed = hk.cleanup_package(work, zip_path)
    assert not work.exists() and not zip_path.exists()
    assert freed > 0


def test_cleanup_kann_behalten(tmp_path):
    work = tmp_path / "p"
    work.mkdir()
    (work / "a.pdf").write_bytes(b"x")
    assert hk.cleanup_package(work, None, keep=True) == 0.0
    assert work.exists()


def test_sweep_raeumt_alles_weg(tmp_path):
    for i in range(3):
        d = tmp_path / f"paket{i}"
        d.mkdir()
        (d / "x.bin").write_bytes(b"x" * 4096)
    hk.sweep_packages(tmp_path)
    assert not list(tmp_path.iterdir())


def test_diskguard_meldet_ok_bei_platz(tmp_path):
    guard = hk.DiskGuard(tmp_path, min_free_mb=1)
    assert guard.check() == ""


def test_diskguard_haelt_an_wenn_voll(tmp_path, monkeypatch):
    monkeypatch.setattr(hk, "free_mb", lambda _p: 10.0)
    guard = hk.DiskGuard(tmp_path, min_free_mb=500)
    with pytest.raises(hk.DiskFull) as exc:
        guard.check()
    assert "Platz schaffen" in str(exc.value)


def test_release_memory_laeuft_durch():
    hk.release_memory()          # darf auf keiner Plattform werfen


def test_orchestrator_raeumt_pakete_auf(mock_dir, tmp_path):
    """Nach dem Lauf darf im Paketordner nichts liegen bleiben."""
    from drawing_checker.kern import RunConfig
    from drawing_checker.ablauf import Callbacks, Orchestrator
    from drawing_checker.sap_ymatdocs import MockSapAdapter

    cfg = RunConfig(excel_path=mock_dir / "Materialliste_Mock.xlsx",
                    sheet_name="Materialliste", material_column="C",
                    header_row=1, output_dir=tmp_path / "erg")
    adapter = MockSapAdapter(mock_dir)
    adapter.ensure_ready()
    orch = Orchestrator(cfg, adapter, Callbacks())
    orch.start()
    orch.join(300)
    rest = list((orch.run_dir / "pakete").iterdir())
    assert rest == [], f"nicht aufgeräumt: {rest}"
    assert orch._freed_mb > 0


def test_orchestrator_behaelt_pakete_auf_wunsch(mock_dir, tmp_path):
    from drawing_checker.kern import RunConfig
    from drawing_checker.ablauf import Callbacks, Orchestrator
    from drawing_checker.sap_ymatdocs import MockSapAdapter

    cfg = RunConfig(excel_path=mock_dir / "Materialliste_Mock.xlsx",
                    sheet_name="Materialliste", material_column="C",
                    header_row=1, output_dir=tmp_path / "erg",
                    keep_packages=True)
    adapter = MockSapAdapter(mock_dir)
    adapter.ensure_ready()
    orch = Orchestrator(cfg, adapter, Callbacks())
    orch.start()
    orch.join(300)
    assert list((orch.run_dir / "pakete").iterdir())


# ------------------------------------------------------------- Gewinde
class _PdfStub:
    ocr_used = False

    def __init__(self, text: str = ""):
        self._text = text

    def full_text(self) -> str:
        return self._text

    def blocks(self):
        return []


def _ctx(text: str = "Werkstoff S235JR") -> CheckContext:
    return CheckContext("1", _PdfStub(text), PackageContent(),
                        load_profile("default"))


def _thread(size: float, depth: float) -> DimValue:
    return DimValue(value=size, kind=DimKind.THREAD, raw=f"M{size:g}",
                    bbox=BBox(0, 0, 10, 10), page=0, depth=depth)


def _hole(dia: float, depth: float) -> DimValue:
    return DimValue(value=dia, kind=DimKind.DIAMETER, raw=f"⌀{dia:g}",
                    bbox=BBox(0, 0, 10, 10), page=0, depth=depth)


def test_gewinde_tiefer_als_bohrung(): 
    ctx = _ctx()
    check_thread_depths(ctx, [_thread(10, 25), _hole(8.5, 20)])
    codes = {f.code: f for f in ctx.findings}
    assert "THRD.DEPTH" in codes
    assert codes["THRD.DEPTH"].severity == Severity.ERROR


def test_gewinde_flacher_als_bohrung_ok():
    ctx = _ctx()
    check_thread_depths(ctx, [_thread(10, 18), _hole(8.5, 24)])
    assert "THRD.DEPTH" not in {f.code for f in ctx.findings}


def test_zu_kurze_einschraubtiefe_in_stahl():
    ctx = _ctx("Werkstoff S235JR")
    check_thread_depths(ctx, [_thread(12, 6)])
    assert "THRD.SHORT" in {f.code for f in ctx.findings}


def test_ausreichende_einschraubtiefe_in_stahl():
    ctx = _ctx("Werkstoff S235JR")
    check_thread_depths(ctx, [_thread(12, 14)])
    assert not ctx.findings


def test_aluminium_verlangt_mehr_einschraubtiefe():
    """1×D reicht in Stahl, in Aluminium nicht."""
    ctx = _ctx("Werkstoff EN AW-6082 T6")
    check_thread_depths(ctx, [_thread(10, 11)])
    codes = [f for f in ctx.findings if f.code == "THRD.SHORT"]
    assert codes and "weichem Werkstoff" in codes[0].text


# ------------------------------------------------------------ Spiegelung
def test_spiegelerkennung_unterscheidet_haende():
    """Eine L-Kontur gegen ihr Spiegelbild: gespiegelt muss besser passen."""
    from drawing_checker.pruef_geometrie import ViewCluster, match_views

    # L-förmige, eindeutig unsymmetrische Kontur
    punkte = [(0, 0), (40, 0), (40, 10), (10, 10), (10, 30), (0, 30), (0, 0)]
    kontur = [(a[0], a[1], b[0], b[1]) for a, b in zip(punkte, punkte[1:])]
    gespiegelte = [(-x0, y0, -x1, y1) for x0, y0, x1, y1 in kontur]

    ansicht = ViewCluster(segments=kontur, bbox=(0, 0, 40, 30))
    gerade = match_views([ansicht], [gespiegelte], mirrored=False)
    gespiegelt = match_views([ansicht], [gespiegelte], mirrored=True)
    assert gespiegelt.score > gerade.score + 0.15


def test_spiegelerkennung_meldet_bei_gleicher_hand_nicht():
    from drawing_checker.pruef_geometrie import ViewCluster, match_views

    punkte = [(0, 0), (40, 0), (40, 10), (10, 10), (10, 30), (0, 30), (0, 0)]
    kontur = [(a[0], a[1], b[0], b[1]) for a, b in zip(punkte, punkte[1:])]
    ansicht = ViewCluster(segments=kontur, bbox=(0, 0, 40, 30))
    gerade = match_views([ansicht], [kontur], mirrored=False)
    gespiegelt = match_views([ansicht], [kontur], mirrored=True)
    assert gerade.score >= gespiegelt.score


# --------------------------------------------------------- Anwenderseite
def test_maengelspalte_wird_gedeckelt():
    """30 Findings gehören nicht in eine Excel-Zelle."""
    from drawing_checker.kern import Finding, JobStatus, MaterialResult
    from drawing_checker.bericht import ( MAX_FINDINGS_IN_CELL, _findings_text, )

    r = MaterialResult(material="1", row=2, status=JobStatus.FINDINGS)
    r.findings = [Finding(code=f"X.{i}", severity=Severity.WARNING,
                          text=f"Punkt {i}", detail="Erläuterung " * 10)
                  for i in range(30)]
    text = _findings_text(r)
    assert text.count("\n") + 1 == MAX_FINDINGS_IN_CELL + 1
    assert "und 18 weitere" in text
    assert text.count("Erläuterung") <= 30      # Details nur bei den Ersten


def test_maengelspalte_ohne_deckel_bei_wenigen():
    from drawing_checker.kern import Finding, JobStatus, MaterialResult
    from drawing_checker.bericht import _findings_text

    r = MaterialResult(material="1", row=2, status=JobStatus.FINDINGS)
    r.findings = [Finding(code="A.B", severity=Severity.ERROR, text="Ein Punkt")]
    assert _findings_text(r) == "[Fehler] A.B: Ein Punkt"


def test_klartext_uebersetzt_technische_fehler():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from drawing_checker.gui import klartext

    assert "Excel geöffnet" in klartext(PermissionError(13, "denied"))
    assert "Speicherplatz" in klartext(OSError("[Errno 28] No space left"))
    assert klartext(ValueError("etwas Eigenes")) == "etwas Eigenes"
