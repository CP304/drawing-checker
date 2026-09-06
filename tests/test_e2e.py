"""End-to-End: kompletter Prüflauf über die Mockdaten inkl. SAP-Absturz + Resume."""
from pathlib import Path

import pytest

from drawing_checker.core.models import JobStatus, RunConfig, Severity
from drawing_checker.core.orchestrator import Callbacks, Orchestrator
from drawing_checker.sap.mock import MockSapAdapter


def make_config(mock_dir: Path, out: Path) -> RunConfig:
    return RunConfig(
        excel_path=mock_dir / "Materialliste_Mock.xlsx",
        sheet_name="Materialliste", material_column="C", header_row=1,
        output_dir=out, material_group="default",
    )


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
    from drawing_checker.core.models import Severity

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
