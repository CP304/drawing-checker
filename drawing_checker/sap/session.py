"""SAP GUI Scripting: Verbindung zu P11 und Ausführung von YMATDOCS.

Nur unter Windows lauffähig (COM). Voraussetzungen:
  * SAP GUI installiert, Scripting client- und serverseitig freigeschaltet
    (sapgui/user_scripting = TRUE – ist laut Basis bereits aktiv).
  * pywin32 installiert (pip install pywin32).

Der konkrete Transaktionsablauf steckt in ymatdocs.py und wird aus dem
.vbs-Mitschnitt der Transaktion portiert (Element-IDs 1:1 übernehmen).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from .adapter import SapAdapter, SapUnavailable
from .watchdog import SapWatchdog

log = logging.getLogger(__name__)


class SapGuiAdapter(SapAdapter):
    def __init__(self, connection_name: str = "P11",
                 saplogon_path: str | None = None):
        self.connection_name = connection_name
        self.watchdog = SapWatchdog(connection_name, saplogon_path)
        self.session = None

    # ------------------------------------------------------------- Anbindung
    def ensure_ready(self) -> None:
        if self.session is not None and self._session_alive():
            return
        self.session = self._attach_or_open()

    def _session_alive(self) -> bool:
        try:
            _ = self.session.Info.SystemName  # wirft bei toter Session
            return True
        except Exception:
            return False

    def _attach_or_open(self):
        """Bestehende P11-Session nutzen, sonst Verbindung öffnen.

        Bei totem SAP GUI übernimmt der Watchdog Neustart + Login.
        """
        try:
            import win32com.client
        except ImportError as exc:  # pragma: no cover - nur auf Nicht-Windows
            raise SapUnavailable(
                "pywin32 fehlt – SAP-Anbindung nur unter Windows möglich"
            ) from exc

        try:
            sapgui = win32com.client.GetObject("SAPGUI")
            app = sapgui.GetScriptingEngine
        except Exception:
            log.info("SAP GUI läuft nicht – Watchdog startet es")
            app = self.watchdog.start_sapgui()

        # Vorhandene Verbindung zum Zielsystem suchen
        for ci in range(app.Children.Count):
            conn = app.Children(ci)
            for si in range(conn.Children.Count):
                sess = conn.Children(si)
                try:
                    if sess.Info.SystemName.upper() in self.connection_name.upper():
                        log.info("Nutze bestehende SAP-Session (%s)",
                                 sess.Info.SystemName)
                        return sess
                except Exception:
                    continue

        log.info("Öffne Verbindung %r", self.connection_name)
        try:
            conn = app.OpenConnection(self.connection_name, True)
        except Exception as exc:
            raise SapUnavailable(
                f"Verbindung {self.connection_name!r} nicht möglich: {exc}"
            ) from exc
        session = conn.Children(0)
        self.watchdog.login_if_needed(session)
        return session

    # ------------------------------------------------------------ Beschaffung
    def fetch_package(self, material: str, target_dir: Path) -> Path:
        from .ymatdocs import run_ymatdocs

        self.ensure_ready()
        try:
            return run_ymatdocs(self.session, material, target_dir)
        except SapUnavailable:
            # Einmaliger Selbstheilungsversuch: neu verbinden und wiederholen.
            log.warning("Session verloren bei %s – Neuverbindung", material)
            self.session = None
            self.watchdog.recover()
            self.ensure_ready()
            return run_ymatdocs(self.session, material, target_dir)

    def close(self) -> None:
        self.session = None


def wait_ready(session, timeout: float = 60.0) -> None:
    """Wartet, bis SAP nicht mehr busy ist; SapUnavailable bei Timeout/COM-Tod."""
    deadline = time.time() + timeout
    while True:
        try:
            if not session.Busy:
                return
        except Exception as exc:
            raise SapUnavailable(f"SAP-Session antwortet nicht: {exc}") from exc
        if time.time() > deadline:
            raise SapUnavailable(f"SAP bleibt busy (> {timeout:.0f}s)")
        time.sleep(0.25)


def find_element(session, element_id: str):
    """FindById ohne Exception; None, wenn das Element nicht existiert."""
    try:
        return session.FindById(element_id, False)
    except Exception:
        return None
