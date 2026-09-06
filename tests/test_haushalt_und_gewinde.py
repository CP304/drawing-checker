"""Tests für den Dauerlauf-Haushalt (Aufräumen, Plattenplatz) und die
Gewinderegeln."""
from __future__ import annotations

from pathlib import Path

import pytest

from drawing_checker.checks.base import CheckContext, load_profile
from drawing_checker.checks.dimension_checks import check_thread_depths
from drawing_checker.core import housekeeping as hk
from drawing_checker.core.models import BBox, PackageContent, Severity
from drawing_checker.drawing.dimensions import DimKind, DimValue


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
    from drawing_checker.core.models import RunConfig
    from drawing_checker.core.orchestrator import Callbacks, Orchestrator
    from drawing_checker.sap.mock import MockSapAdapter

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
    from drawing_checker.core.models import RunConfig
    from drawing_checker.core.orchestrator import Callbacks, Orchestrator
    from drawing_checker.sap.mock import MockSapAdapter

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
    from drawing_checker.checks.contour_projection import ViewCluster, match_views

    # L-förmige, eindeutig unsymmetrische Kontur
    punkte = [(0, 0), (40, 0), (40, 10), (10, 10), (10, 30), (0, 30), (0, 0)]
    kontur = [(a[0], a[1], b[0], b[1]) for a, b in zip(punkte, punkte[1:])]
    gespiegelte = [(-x0, y0, -x1, y1) for x0, y0, x1, y1 in kontur]

    ansicht = ViewCluster(segments=kontur, bbox=(0, 0, 40, 30))
    gerade = match_views([ansicht], [gespiegelte], mirrored=False)
    gespiegelt = match_views([ansicht], [gespiegelte], mirrored=True)
    assert gespiegelt.score > gerade.score + 0.15


def test_spiegelerkennung_meldet_bei_gleicher_hand_nicht():
    from drawing_checker.checks.contour_projection import ViewCluster, match_views

    punkte = [(0, 0), (40, 0), (40, 10), (10, 10), (10, 30), (0, 30), (0, 0)]
    kontur = [(a[0], a[1], b[0], b[1]) for a, b in zip(punkte, punkte[1:])]
    ansicht = ViewCluster(segments=kontur, bbox=(0, 0, 40, 30))
    gerade = match_views([ansicht], [kontur], mirrored=False)
    gespiegelt = match_views([ansicht], [kontur], mirrored=True)
    assert gerade.score >= gespiegelt.score


# --------------------------------------------------------- Anwenderseite
def test_maengelspalte_wird_gedeckelt():
    """30 Findings gehören nicht in eine Excel-Zelle."""
    from drawing_checker.core.models import Finding, JobStatus, MaterialResult
    from drawing_checker.report.excel_writer import (
        MAX_FINDINGS_IN_CELL, _findings_text,
    )

    r = MaterialResult(material="1", row=2, status=JobStatus.FINDINGS)
    r.findings = [Finding(code=f"X.{i}", severity=Severity.WARNING,
                          text=f"Punkt {i}", detail="Erläuterung " * 10)
                  for i in range(30)]
    text = _findings_text(r)
    assert text.count("\n") + 1 == MAX_FINDINGS_IN_CELL + 1
    assert "und 18 weitere" in text
    assert text.count("Erläuterung") <= 30      # Details nur bei den Ersten


def test_maengelspalte_ohne_deckel_bei_wenigen():
    from drawing_checker.core.models import Finding, JobStatus, MaterialResult
    from drawing_checker.report.excel_writer import _findings_text

    r = MaterialResult(material="1", row=2, status=JobStatus.FINDINGS)
    r.findings = [Finding(code="A.B", severity=Severity.ERROR, text="Ein Punkt")]
    assert _findings_text(r) == "[Fehler] A.B: Ein Punkt"


def test_klartext_uebersetzt_technische_fehler():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from drawing_checker.gui.main_window import klartext

    assert "Excel geöffnet" in klartext(PermissionError(13, "denied"))
    assert "Speicherplatz" in klartext(OSError("[Errno 28] No space left"))
    assert klartext(ValueError("etwas Eigenes")) == "etwas Eigenes"
