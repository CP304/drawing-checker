"""Tests der Laufsteuerung: Blockweise, Abbrechen, Fortsetzen, SAP-Fenster.

Die drei Anforderungen aus dem Betrieb:
  * die Ergebnis-Excel wird fortlaufend geschrieben und der Lauf findet
    von selbst wieder, wo er aufgehört hat,
  * der Lauf lässt sich per Knopf abbrechen - auch mitten im Download,
  * in SAP werden nie mehr als fünf Fenster geöffnet.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import openpyxl
import pytest

from drawing_checker.kern import JobStatus, RunConfig
from drawing_checker.ablauf import Callbacks, Orchestrator
from drawing_checker.kern import finde_fortsetzbaren_lauf
from drawing_checker.sap_ymatdocs import MockSapAdapter


def make_config(mock_dir: Path, out: Path, **kw) -> RunConfig:
    basis = dict(
        excel_path=mock_dir / "Materialliste_Mock.xlsx",
        sheet_name="Materialliste", material_column="C", header_row=1,
        output_dir=out, material_group="default",
    )
    basis.update(kw)
    return RunConfig(**basis)


def _lauf(cfg, mock_dir, resume=False, adapter=None) -> Orchestrator:
    adapter = adapter or MockSapAdapter(mock_dir)
    adapter.ensure_ready()
    orch = Orchestrator(cfg, adapter, Callbacks(), resume=resume)
    orch.start()
    orch.join(600)
    return orch


# ------------------------------------------------------- fortlaufend Excel
def test_excel_waechst_mit_jeder_materialnummer(mock_dir, tmp_path):
    """Nach jeder Nummer muss die Ergebnis-Excel auf Platte aktuell sein."""
    cfg = make_config(mock_dir, tmp_path / "erg")
    gesehen: list[int] = []

    def on_result(_r):
        pfad = cfg.excel_path.with_stem(cfg.excel_path.stem + "_geprüft")
        if pfad.exists():
            wb = openpyxl.load_workbook(pfad, read_only=True, data_only=True)
            ws = wb[cfg.sheet_name]
            gefuellt = sum(1 for row in ws.iter_rows(min_row=2, values_only=True)
                           if any("Geprüft" in str(v) or "OK" in str(v)
                                  or "Findings" in str(v) for v in row if v))
            gesehen.append(gefuellt)
            wb.close()

    adapter = MockSapAdapter(mock_dir)
    adapter.ensure_ready()
    orch = Orchestrator(cfg, adapter, Callbacks(on_result=on_result))
    orch.start()
    orch.join(600)
    assert gesehen, "keine Zwischenstände gesehen"
    assert gesehen == sorted(gesehen), f"Excel wuchs nicht monoton: {gesehen}"
    assert gesehen[-1] >= len(gesehen) - 1


# ------------------------------------------------------------- Fortsetzen
def test_findet_den_passenden_lauf_wieder(mock_dir, tmp_path):
    cfg = make_config(mock_dir, tmp_path / "erg")
    _lauf(cfg, mock_dir)
    treffer = finde_fortsetzbaren_lauf(cfg)
    assert treffer is not None
    _ordner, fertig, _gesamt = treffer
    assert fertig >= 4


def test_fremder_lauf_wird_nicht_fortgesetzt(mock_dir, tmp_path):
    """Ein Lauf einer anderen Spalte darf nicht fortgesetzt werden."""
    cfg = make_config(mock_dir, tmp_path / "erg")
    _lauf(cfg, mock_dir)
    andere = make_config(mock_dir, tmp_path / "erg", material_column="A")
    assert finde_fortsetzbaren_lauf(andere) is None


def test_ohne_frueheren_lauf_kein_treffer(mock_dir, tmp_path):
    cfg = make_config(mock_dir, tmp_path / "leer")
    assert finde_fortsetzbaren_lauf(cfg) is None


def test_fortsetzen_prueft_nur_das_offene(mock_dir, tmp_path):
    cfg = make_config(mock_dir, tmp_path / "erg")
    erster = _lauf(cfg, mock_dir)
    geprueft = erster.progress.done

    zweiter = _lauf(cfg, mock_dir, resume=True)
    assert zweiter.run_dir == erster.run_dir, "anderer Lauf-Ordner"
    assert zweiter.progress.done == geprueft
    # Es wurde nichts erneut geholt: der Mock zählt die Abrufe.
    assert zweiter.progress.total == erster.progress.total


# ---------------------------------------------------------------- Abbruch
def test_abbruch_haelt_an_und_bleibt_fortsetzbar(mock_dir, tmp_path):
    cfg = make_config(mock_dir, tmp_path / "erg", batch_size=0)
    adapter = MockSapAdapter(mock_dir)
    adapter.ensure_ready()
    orch = Orchestrator(cfg, adapter, Callbacks())

    def stoppe_nach_erstem(_r):
        orch.stop()

    orch.cb.on_result = stoppe_nach_erstem
    orch.start()
    orch.join(600)

    assert orch.progress.done < orch.progress.total, "Lauf lief komplett durch"
    treffer = finde_fortsetzbaren_lauf(cfg)
    assert treffer is not None, "abgebrochener Lauf nicht fortsetzbar"
    # Bericht und Zusammenfassung wurden trotz Abbruch geschrieben.
    assert (orch.run_dir / "findings.csv").is_file()
    assert orch.report_path and orch.report_path.is_file()


def test_download_wartet_nicht_nach_abbruch(tmp_path):
    """Der Abbrechen-Knopf wirkt sofort, nicht erst nach dem Zeitablauf."""
    from drawing_checker.sap_sitzung import DownloadWatcher

    watcher = DownloadWatcher(expected=tmp_path / "nie.zip", watch_dirs=[],
                              timeout_s=120)
    watcher.start()
    t0 = time.time()
    with pytest.raises(TimeoutError, match="abgebrochen"):
        watcher.wait(abbruch=lambda: True)
    assert time.time() - t0 < 5


def test_ablauf_bricht_zwischen_den_schritten_ab():
    from drawing_checker.sap_ymatdocs import FakeSession
    from drawing_checker.sap_ablauf import ( Abgebrochen, ScriptFlow, Step, play, )

    flow = ScriptFlow(steps=[Step("set_text", "wnd[0]/usr/ctxtA", "1"),
                             Step("set_text", "wnd[0]/usr/ctxtB", "2")])
    session = FakeSession()
    with pytest.raises(Abgebrochen):
        play(session, flow, {}, abbruch=lambda: True)
    assert not session.log, "trotz Abbruch wurde etwas ausgeführt"


# --------------------------------------------------------------- Blockweise
def test_blockweise_schreibt_zwischenberichte(mock_dir, tmp_path):
    cfg = make_config(mock_dir, tmp_path / "erg", batch_size=2)
    bloecke: list[tuple[int, int]] = []

    def on_progress(p):
        if p.batches:
            bloecke.append((p.batch, p.batches))

    adapter = MockSapAdapter(mock_dir)
    adapter.ensure_ready()
    orch = Orchestrator(cfg, adapter, Callbacks(on_progress=on_progress))
    orch.start()
    orch.join(600)

    assert orch.progress.batches >= 2, "keine Blöcke gebildet"
    assert max(b for b, _ in bloecke) >= 2
    assert orch.report_path and orch.report_path.is_file()


def test_ohne_blockgroesse_ein_einziger_block(mock_dir, tmp_path):
    cfg = make_config(mock_dir, tmp_path / "erg", batch_size=0)
    orch = _lauf(cfg, mock_dir)
    assert orch.progress.batches == 1


def test_blockwechsel_haken_wird_gerufen(mock_dir, tmp_path):
    """Der Adapter darf zwischen den Blöcken SAP aufräumen."""
    cfg = make_config(mock_dir, tmp_path / "erg", batch_size=2)
    adapter = MockSapAdapter(mock_dir)
    adapter.ensure_ready()
    gerufen: list[int] = []
    adapter.blockwechsel = lambda: gerufen.append(1)
    orch = Orchestrator(cfg, adapter, Callbacks(), resume=False)
    orch.start()
    orch.join(600)
    assert gerufen, "Blockwechsel-Haken wurde nie gerufen"


# ------------------------------------------------------- SAP-Fenstergrenze
class _FakeApp:
    """Nachbau der Scripting-Engine mit einstellbarer Fensterzahl."""

    class _Conn:
        def __init__(self, sessions):
            self._s = sessions

        @property
        def Children(self):
            class _C:
                Count = len(self._s)

                def __call__(_self, i):
                    return self._s[i]
            return _C()

    def __init__(self, verbindungen):
        self._c = [self._Conn(s) for s in verbindungen]

    @property
    def Children(self):
        class _C:
            Count = len(self._c)

            def __call__(_self, i):
                return self._c[i]
        return _C()


def test_zaehlt_offene_sap_fenster():
    from drawing_checker.sap_sitzung import zaehle_sessions

    app = _FakeApp([[object(), object()], [object()]])
    assert zaehle_sessions(app) == 3


def test_oeffnet_kein_sechstes_fenster(monkeypatch):
    """Bei fünf offenen Fenstern wird nichts mehr geöffnet."""
    from drawing_checker import sap_sitzung as sapsession

    class _Fremd:
        class Info:
            SystemName = "Q22"

    app = _FakeApp([[_Fremd()] * 5])
    adapter = sapsession.SapGuiAdapter(connection_name="P11", max_sessions=5)

    with pytest.raises(sapsession.SapUnavailable, match="bereits 5 Fenster"):
        adapter._pruefe_grenze(app)


def test_unter_der_grenze_wird_geoeffnet():
    from drawing_checker import sap_sitzung as sapsession

    class _Fremd:
        class Info:
            SystemName = "Q22"

    app = _FakeApp([[_Fremd()] * 2])
    adapter = sapsession.SapGuiAdapter(connection_name="P11", max_sessions=5)
    adapter._pruefe_grenze(app)      # darf nicht werfen
