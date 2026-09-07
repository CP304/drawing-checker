"""Tests der SAP-Schicht ohne SAP: Parser, Player, Popups, Download.

Der komplette Durchstich (Mitschnitt einlesen -> abspielen -> Paket liegt
am Zielort) wird gegen die simulierte Session geprüft. Damit ist am
Einsatztag nur noch der echte .vbs-Mitschnitt einzusetzen.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from drawing_checker import sap_cli
from drawing_checker.sap_sitzung import DownloadWatcher
from drawing_checker.sap_ymatdocs import FakeSession
from drawing_checker.sap_sitzung import handle_popups
from drawing_checker.sap_ablauf import FlowError, ScriptFlow, Step, play
from drawing_checker.sap_ablauf import describe, parse_vbs
from drawing_checker.sap_ymatdocs import run_ymatdocs

FIXTURE = Path(__file__).parent / "fixtures" / "ymatdocs_beispiel.vbs"


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
