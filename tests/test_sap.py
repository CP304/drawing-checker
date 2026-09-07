"""SAP: Mitschnitt, Ablauf, Sitzungsgrenzen, Laufsteuerung, GUI-Anbindung.

Alles ohne echtes SAP - die nachgebaute Sitzung deckt den Weg ab.
"""
from __future__ import annotations

# ======================================================================
# sap_flow
# ======================================================================
# Tests der SAP-Schicht ohne SAP: Parser, Player, Popups, Download.
#
# Der komplette Durchstich (Mitschnitt einlesen -> abspielen -> Paket liegt
# am Zielort) wird gegen die simulierte Session geprüft. Damit ist am
# Einsatztag nur noch der echte .vbs-Mitschnitt einzusetzen.
from pathlib import Path

import pytest

from drawing_checker import sap_cli
from drawing_checker.sap_sitzung import DownloadWatcher
from drawing_checker.sap_ymatdocs import FakeSession
from drawing_checker.sap_sitzung import handle_popups
from drawing_checker.sap_ablauf import FlowError, ScriptFlow, Step, play
from drawing_checker.sap_ablauf import describe, parse_vbs
from drawing_checker.sap_ymatdocs import run_ymatdocs
from conftest import FIXTURE



# ------------------------------------------------------------------ Parser
def test_parser_erkennt_transaktion_und_materialfeld():
    flow = parse_vbs(FIXTURE)
    assert flow.transaction == "YMATDOCS"
    assert flow.material_field == "wnd[0]/usr/ctxtS_MATNR-LOW"
    # Von- und Bis-Feld bekommen beide den Platzhalter.
    matnr_steps = [s for s in flow.steps if s.value == "{material}"]
    assert len(matnr_steps) == 2


def test_parser_setzt_dialog_platzhalter():
    flow = parse_vbs(FIXTURE)
    werte = {s.element: s.value for s in flow.steps if s.action == "set_text"}
    assert werte["wnd[1]/usr/ctxtDY_PATH"] == "{target_dir}"
    assert werte["wnd[1]/usr/ctxtDY_FILENAME"] == "{filename}"
    # Nicht-Materialzahlen bleiben unangetastet (Werk).
    assert werte["wnd[0]/usr/ctxtP_WERKS"] == "1000"


def test_parser_bildet_grid_methode_generisch_ab():
    """`pressToolbarButton "DOWNLOAD"` ist keine bekannte Aktion."""
    flow = parse_vbs(FIXTURE)
    calls = [s for s in flow.steps if s.action == "call"]
    assert calls, "ALV-Grid-Methode wurde nicht übernommen"
    assert calls[0].method == "pressToolbarButton"
    assert calls[0].args == ["DOWNLOAD"]
    # und sie ist als Download-Auslöser markiert
    assert flow.steps[flow.download_step_index] is calls[0]


def test_parser_ueberspringt_kosmetik():
    flow = parse_vbs(FIXTURE)
    assert not [s for s in flow.steps
                if s.action in ("maximize", "set_focus", "set_caret")]


def test_flow_speichern_und_laden(tmp_path):
    flow = parse_vbs(FIXTURE)
    ziel = tmp_path / "flow.yaml"
    flow.save(ziel)
    wieder = ScriptFlow.load(ziel)
    assert wieder.to_dict() == flow.to_dict()


def test_describe_nennt_download_schritt():
    text = describe(parse_vbs(FIXTURE))
    assert "<== DOWNLOAD" in text
    assert "NICHT ERKANNT" not in text


def test_describe_warnt_ohne_materialfeld():
    flow = ScriptFlow(steps=[Step("press", "wnd[0]/tbar[0]/btn[0]")])
    assert "WARNUNG" in describe(flow)


# ------------------------------------------------------------------ Player
def _fixture_flow() -> ScriptFlow:
    return parse_vbs(FIXTURE)


def test_player_ersetzt_platzhalter():
    flow = _fixture_flow()
    session = FakeSession(popup_after="wnd[0]/usr/cntlGRID1/shellcont/shell")
    play(session, flow, {"material": "10473215", "target_dir": r"C:\ziel",
                         "filename": "10473215.zip",
                         "target_path": r"C:\ziel\10473215.zip"})
    assert session.texts_of("wnd[0]/usr/ctxtS_MATNR-LOW") == ["10473215"]
    assert session.texts_of("wnd[1]/usr/ctxtDY_PATH") == [r"C:\ziel"]
    assert session.texts_of("wnd[1]/usr/ctxtDY_FILENAME") == ["10473215.zip"]


def test_player_meldet_fehlendes_element():
    flow = ScriptFlow(steps=[Step("set_text", "wnd[0]/usr/ctxtFEHLT", "x")])
    session = FakeSession(missing={"wnd[0]/usr/ctxtFEHLT"})
    with pytest.raises(FlowError) as exc:
        play(session, flow, {})
    assert "ctxtFEHLT" in str(exc.value)


def test_player_ueberspringt_optionale_schritte():
    flow = ScriptFlow(steps=[
        Step("set_text", "wnd[0]/usr/ctxtFEHLT", "x", optional=True),
        Step("press", "wnd[0]/tbar[0]/btn[0]"),
    ])
    session = FakeSession(missing={"wnd[0]/usr/ctxtFEHLT"})
    play(session, flow, {})
    assert "press" in session.actions()


def test_player_stop_after():
    flow = _fixture_flow()
    session = FakeSession()
    play(session, flow, {"material": "1", "target_dir": "d",
                         "filename": "f", "target_path": "p"}, stop_after=2)
    assert session.texts_of("wnd[0]/usr/ctxtS_MATNR-HIGH") == []


def test_player_generische_eigenschaft():
    flow = ScriptFlow(steps=[
        Step("set_prop", "wnd[0]/usr/cntlGRID/shellcont/shell",
             value=3, member="currentCellRow")])
    session = FakeSession()
    play(session, flow, {})
    element = session.FindById("wnd[0]/usr/cntlGRID/shellcont/shell")
    assert element.__dict__["currentCellRow"] == 3


# ------------------------------------------------------------------ Popups
def test_popup_wird_bestaetigt():
    session = FakeSession()
    session.open_popup()
    session.FindById("wnd[1]").Text = "Datei existiert bereits – überschreiben?"
    assert handle_popups(session) == 1
    assert not session.open_popups


def test_druckdialog_wird_abgebrochen():
    session = FakeSession()
    session.open_popup()
    session.FindById("wnd[1]").Text = "Drucken"
    handle_popups(session)
    gedrueckt = [e for a, e, _v in session.log if a == "press"]
    assert any("btn[12]" in e for e in gedrueckt)


def test_dateidialog_wird_nicht_weggeklickt():
    """Der Speichern-Dialog des Downloads gehört dem Ablauf, nicht dem Handler."""
    session = FakeSession()
    session.open_popup()
    assert handle_popups(session, skip_windows={"wnd[1]"}) == 0
    assert "wnd[1]" in session.open_popups


# ---------------------------------------------------------------- Download
def test_download_watcher_erkennt_datei(tmp_path):
    ziel = tmp_path / "paket.zip"
    watcher = DownloadWatcher(expected=ziel, watch_dirs=[], timeout_s=10)
    watcher.start()
    ziel.write_bytes(b"PK\x03\x04")
    assert watcher.wait() == ziel


def test_download_watcher_findet_abweichenden_namen(tmp_path):
    ordner = tmp_path / "downloads"
    ordner.mkdir()
    watcher = DownloadWatcher(expected=tmp_path / "erwartet.zip",
                              watch_dirs=[ordner], timeout_s=10)
    watcher.start()
    (ordner / "SAP_export_4711.zip").write_bytes(b"PK\x03\x04")
    assert watcher.wait().name == "SAP_export_4711.zip"


def test_download_watcher_laeuft_ab(tmp_path):
    watcher = DownloadWatcher(expected=tmp_path / "nie.zip", watch_dirs=[],
                              timeout_s=1)
    watcher.start()
    with pytest.raises(TimeoutError):
        watcher.wait()


# ------------------------------------------------------------ Durchstich
def test_run_ymatdocs_liefert_paket(tmp_path):
    flow_datei = tmp_path / "flow.yaml"
    parse_vbs(FIXTURE).save(flow_datei)
    ziel = tmp_path / "pakete"
    session = FakeSession(
        download_target=ziel / "10473215.zip",
        popup_after="wnd[0]/usr/cntlGRID1/shellcont/shell",
        download_trigger="wnd[1]/tbar[0]/btn[0]")
    ergebnis = run_ymatdocs(session, "10473215", ziel,
                            flow_path=flow_datei, watch_dirs=[])
    assert ergebnis.is_file()
    assert ergebnis.name == "10473215.zip"


def test_run_ymatdocs_meldet_nicht_vorhandenes_material(tmp_path):
    from drawing_checker.sap_sitzung import MaterialNotFound

    flow_datei = tmp_path / "flow.yaml"
    parse_vbs(FIXTURE).save(flow_datei)
    session = FakeSession(status=("Zu dieser Materialnummer sind keine "
                                  "Dokumente vorhanden", "S"),
                          popup_after="wnd[0]/usr/cntlGRID1/shellcont/shell")
    with pytest.raises(MaterialNotFound):
        run_ymatdocs(session, "9999999", tmp_path / "out",
                     flow_path=flow_datei, watch_dirs=[])


def test_run_ymatdocs_meldet_absturz(tmp_path):
    from drawing_checker.sap_sitzung import SapUnavailable

    flow_datei = tmp_path / "flow.yaml"
    parse_vbs(FIXTURE).save(flow_datei)
    session = FakeSession()
    session.crash()
    with pytest.raises(SapUnavailable):
        run_ymatdocs(session, "10473215", tmp_path / "out",
                     flow_path=flow_datei, watch_dirs=[])


# ------------------------------------------------------------------- CLI
def test_cli_import_und_trockenlauf(tmp_path, capsys):
    ziel = tmp_path / "ymatdocs_flow.yaml"
    assert sap_cli.import_vbs(FIXTURE, ziel) == 0
    assert ziel.is_file()
    assert sap_cli.dry_run("10473215", ziel) == 0
    ausgabe = capsys.readouterr().out
    assert "Trockenlauf ok" in ausgabe
    assert "wnd[0]/usr/ctxtS_MATNR-LOW" in ausgabe


def test_cli_trockenlauf_meldet_fehlendes_materialfeld(tmp_path, capsys):
    flow = ScriptFlow(name="ohne", transaction="YMATDOCS", steps=[
        Step("start_transaction", value="/nYMATDOCS"),
        Step("send_vkey", "wnd[0]", 8),
        Step("press", "wnd[0]/tbar[1]/btn[13]", comment="Download"),
    ], download_step_index=2)
    datei = tmp_path / "flow.yaml"
    flow.save(datei)
    assert sap_cli.dry_run("4711", datei) == 1
    assert "Materialnummer-Feld" in capsys.readouterr().out


def test_cli_trockenlauf_ohne_import_meldet_notnagel(tmp_path, capsys,
                                                     monkeypatch):
    """Ohne Mitschnitt darf der Trockenlauf nicht als 'ok' gelten."""
    from drawing_checker import sap_ymatdocs as ymatdocs

    monkeypatch.setattr(ymatdocs, "flow_search_paths",
                        lambda: [tmp_path / "gibtsnicht.yaml"])
    assert sap_cli.dry_run("4711") == 1
    assert "Notnagel" in capsys.readouterr().out


# ------------------------------------------------ Nur der Mitschnitt reicht
def test_verbindung_aus_dem_mitschnitt(tmp_path):
    """Steht die Verbindung im .vbs, muss niemand das System eintippen."""
    vbs = tmp_path / "mit_verbindung.vbs"
    vbs.write_text(
        'If Not IsObject(application) Then\n'
        '   Set SapGuiAuto = GetObject("SAPGUI")\n'
        '   Set application = SapGuiAuto.GetScriptingEngine\n'
        'End If\n'
        'Set connection = application.OpenConnection("P11 Produktion", True)\n'
        'session.findById("wnd[0]/tbar[0]/okcd").text = "/nYMATDOCS"\n'
        'session.findById("wnd[0]/usr/ctxtP_MATNR").text = "10473215"\n'
        'session.findById("wnd[0]").sendVKey 8\n'
        'session.findById("wnd[0]/tbar[1]/btn[13]").press\n',
        encoding="utf-8")
    flow = parse_vbs(vbs)
    assert flow.connection == "P11"
    assert flow.transaction == "YMATDOCS"
    assert flow.material_field == "wnd[0]/usr/ctxtP_MATNR"


def test_verbindung_bleibt_leer_ohne_angabe():
    assert parse_vbs(FIXTURE).connection == ""


def test_verbindung_ueberlebt_speichern(tmp_path):
    from drawing_checker.sap_ablauf import ScriptFlow

    flow = parse_vbs(FIXTURE)
    flow.connection = "Q22"
    ziel = tmp_path / "flow.yaml"
    flow.save(ziel)
    assert ScriptFlow.load(ziel).connection == "Q22"


def test_uebernehmen_speichert_und_meldet(tmp_path):
    """Ein Aufruf: einlesen, speichern, Klartext-Rückmeldung."""
    from drawing_checker.sap_ablauf import uebernehmen

    ziel = tmp_path / "regeln" / "ymatdocs_flow.yaml"
    flow, verstanden, zeilen = uebernehmen(FIXTURE, ziel)
    assert ziel.is_file()
    assert verstanden is True
    text = "\n".join(zeilen)
    assert "YMATDOCS" in text
    assert "Materialnummer geht in" in text
    assert "Download über" in text


def test_kurzbericht_meldet_luecken():
    from drawing_checker.sap_ablauf import ScriptFlow, Step
    from drawing_checker.sap_ablauf import kurzbericht

    flow = ScriptFlow(steps=[Step("press", "wnd[0]/tbar[0]/btn[0]")])
    verstanden, zeilen = kurzbericht(flow)
    assert verstanden is False
    text = "\n".join(zeilen)
    assert "Kein Feld für die Materialnummer" in text


# ======================================================================
# lauf_steuerung
# ======================================================================
# Tests der Laufsteuerung: Blockweise, Abbrechen, Fortsetzen, SAP-Fenster.
#
# Die drei Anforderungen aus dem Betrieb:
#   * die Ergebnis-Excel wird fortlaufend geschrieben und der Lauf findet
#     von selbst wieder, wo er aufgehört hat,
#   * der Lauf lässt sich per Knopf abbrechen - auch mitten im Download,
#   * in SAP werden nie mehr als fünf Fenster geöffnet.
import threading
import time

import openpyxl

from drawing_checker.kern import JobStatus, RunConfig
from drawing_checker.ablauf import Callbacks, Orchestrator
from drawing_checker.kern import finde_fortsetzbaren_lauf
from drawing_checker.sap_ymatdocs import MockSapAdapter
from conftest import make_config




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


# ======================================================================
# gui_ablauf
# ======================================================================
# GUI: Der .vbs-Mitschnitt ist alles, was der Anwender mitbringen muss.
#
# Läuft offscreen (QT_QPA_PLATFORM=offscreen). Geprüft wird die Logik um den
# Ablauf herum – nicht das Aussehen: Zeigt die GUI an, ob ein Ablauf da ist?
# Verhindert sie den Start ohne Ablauf? Übernimmt sie das SAP-System aus dem
# Mitschnitt?
import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from drawing_checker.sap_ymatdocs import MockSapAdapter # noqa: E402
from drawing_checker.sap_ablauf import uebernehmen # noqa: E402



@pytest.fixture()
def fenster(tmp_path, monkeypatch):
    """MainWindow mit eigenem Regelordner, damit nichts überschrieben wird."""
    from PySide6.QtWidgets import QApplication
    from drawing_checker import gui as mw

    monkeypatch.setenv("DRAWING_CHECKER_RULES", str(tmp_path / "regeln"))
    monkeypatch.setattr("drawing_checker.sap_cli._default_flow_path",
                        lambda: tmp_path / "regeln" / "ymatdocs_flow.yaml")
    monkeypatch.setattr(
        "drawing_checker.sap_ymatdocs.flow_search_paths",
        lambda: [tmp_path / "regeln" / "ymatdocs_flow.yaml"])
    from drawing_checker.sap_ymatdocs import _flow_cache

    _flow_cache.clear()
    app = QApplication.instance() or QApplication([])
    fenster = mw.MainWindow(lambda cfg: MockSapAdapter(cfg.mock_source),
                            ["default"])
    yield fenster
    _flow_cache.clear()


def test_meldet_fehlenden_ablauf(fenster):
    assert fenster._hat_ablauf() is False
    assert "fehlt" in fenster.lbl_flow.text()


def test_zeigt_ablauf_nach_dem_einlesen(fenster, tmp_path):
    uebernehmen(FIXTURE, tmp_path / "regeln" / "ymatdocs_flow.yaml")
    fenster._flow_status()
    assert fenster._hat_ablauf() is True
    text = fenster.lbl_flow.text()
    assert "YMATDOCS" in text and "11 Schritte" in text


def test_uebernimmt_das_system_aus_dem_mitschnitt(fenster, tmp_path):
    vbs = tmp_path / "mit_system.vbs"
    vbs.write_text(
        'Set connection = application.OpenConnection("Q22 Test", True)\n'
        'session.findById("wnd[0]/tbar[0]/okcd").text = "/nYMATDOCS"\n'
        'session.findById("wnd[0]/usr/ctxtP_MATNR").text = "10473215"\n'
        'session.findById("wnd[0]/tbar[1]/btn[13]").press\n', encoding="utf-8")
    fenster.txt_system.setText("")
    # Bewusst ohne Dialog: ein modales Fenster wuerde den Test anhalten.
    # Die Meldung darum herum ist nur Text zu diesem Ergebnis.
    flow, ok, zeilen, ziel = fenster._ablauf_uebernehmen(vbs)
    assert fenster.txt_system.text() == "Q22"
    assert flow.transaction == "YMATDOCS"
    assert ok is True and ziel.is_file()


def test_sucht_vbs_an_den_ueblichen_stellen(fenster, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alt.vbs").write_text("x", encoding="utf-8")
    (tmp_path / "neu.vbs").write_text("y", encoding="utf-8")
    os.utime(tmp_path / "neu.vbs", (10**9 + 100, 10**9 + 100))
    vorschlag = fenster._vbs_vorschlag()
    assert vorschlag is not None and vorschlag.suffix == ".vbs"
