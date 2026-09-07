"""GUI: Der .vbs-Mitschnitt ist alles, was der Anwender mitbringen muss.

Läuft offscreen (QT_QPA_PLATFORM=offscreen). Geprüft wird die Logik um den
Ablauf herum – nicht das Aussehen: Zeigt die GUI an, ob ein Ablauf da ist?
Verhindert sie den Start ohne Ablauf? Übernimmt sie das SAP-System aus dem
Mitschnitt?
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from drawing_checker.sap.mock import MockSapAdapter          # noqa: E402
from drawing_checker.sap.vbs_parser import uebernehmen       # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "ymatdocs_beispiel.vbs"


@pytest.fixture()
def fenster(tmp_path, monkeypatch):
    """MainWindow mit eigenem Regelordner, damit nichts überschrieben wird."""
    from PySide6.QtWidgets import QApplication
    from drawing_checker.gui import main_window as mw

    monkeypatch.setenv("DRAWING_CHECKER_RULES", str(tmp_path / "regeln"))
    monkeypatch.setattr("drawing_checker.sap.cli._default_flow_path",
                        lambda: tmp_path / "regeln" / "ymatdocs_flow.yaml")
    monkeypatch.setattr(
        "drawing_checker.sap.ymatdocs.flow_search_paths",
        lambda: [tmp_path / "regeln" / "ymatdocs_flow.yaml"])
    from drawing_checker.sap.ymatdocs import _flow_cache

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
