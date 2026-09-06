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

# SAP erlaubt je Anmeldung nur eine begrenzte Zahl von Modi (Fenstern) –
# üblich sind 6. Der Checker bleibt bewusst darunter, damit der Anwender
# parallel weiterarbeiten kann und kein Fenster verloren geht. Wird die
# Grenze erreicht, oeffnet der Checker KEIN weiteres, sondern meldet es.
DEFAULT_MAX_SESSIONS = 5


class SapGuiAdapter(SapAdapter):
    def __init__(self, connection_name: str = "P11",
                 saplogon_path: str | None = None,
                 flow_path: Path | None = None,
                 diagnose_dir: Path | None = None,
                 watch_dirs: list[Path] | None = None,
                 max_sessions: int = DEFAULT_MAX_SESSIONS):
        self.connection_name = connection_name
        self.watchdog = SapWatchdog(connection_name, saplogon_path)
        self.session = None
        self.flow_path = flow_path
        self.diagnose_dir = diagnose_dir
        self.watch_dirs = watch_dirs
        self.max_sessions = max_sessions
        # Vom Checker selbst geöffnete Session: die wird am Ende wieder
        # geschlossen, damit über mehrere Läufe keine Fenster auflaufen.
        self._selbst_geoeffnet = False
        # Wird vom Orchestrator gesetzt: liefert True, wenn abgebrochen
        # werden soll (Knopf in der GUI).
        self.stop_event = None

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

        # Vorhandene Session zum Zielsystem wiederverwenden – das ist der
        # Normalfall und öffnet gar kein neues Fenster.
        vorhanden = zaehle_sessions(app)
        for ci in range(app.Children.Count):
            conn = app.Children(ci)
            for si in range(conn.Children.Count):
                sess = conn.Children(si)
                try:
                    if sess.Info.SystemName.upper() in self.connection_name.upper():
                        log.info("Nutze bestehende SAP-Session (%s), %d Fenster "
                                 "offen", sess.Info.SystemName, vorhanden)
                        return sess
                except Exception:
                    continue

        self._pruefe_grenze(app)

        log.info("Öffne Verbindung %r (bisher %d Fenster offen)",
                 self.connection_name, vorhanden)
        try:
            conn = app.OpenConnection(self.connection_name, True)
        except Exception as exc:
            raise SapUnavailable(
                f"Verbindung {self.connection_name!r} nicht möglich: {exc}"
            ) from exc
        session = conn.Children(0)
        self._selbst_geoeffnet = True
        self.watchdog.login_if_needed(session)
        return session

    # ------------------------------------------------------------ Beschaffung
    def fetch_package(self, material: str, target_dir: Path) -> Path:
        from .ymatdocs import run_ymatdocs

        self.ensure_ready()
        try:
            return self._run(material, target_dir)
        except SapUnavailable:
            # Einmaliger Selbstheilungsversuch: neu verbinden und wiederholen.
            log.warning("Session verloren bei %s – Neuverbindung", material)
            self._write_diagnosis(material)
            self.session = None
            self.watchdog.recover()
            self.ensure_ready()
            return self._run(material, target_dir)

    def _run(self, material: str, target_dir: Path) -> Path:
        from .ymatdocs import run_ymatdocs

        return run_ymatdocs(self.session, material, target_dir,
                            flow_path=self.flow_path,
                            watch_dirs=self.watch_dirs,
                            abbruch=self._abbruch)

    def _abbruch(self) -> bool:
        """True, sobald der Anwender in der GUI auf Abbrechen gedrückt hat."""
        ev = self.stop_event
        return bool(ev is not None and ev.is_set())

    def _write_diagnosis(self, material: str) -> None:
        """Bei technischen Fehlern Elementbaum und Bildschirmfoto sichern."""
        if self.diagnose_dir is None or self.session is None:
            return
        try:
            from .diagnostics import diagnose_failure

            diagnose_failure(self.session, material, self.diagnose_dir)
        except Exception:
            log.debug("Diagnose konnte nicht geschrieben werden",
                      exc_info=True)

    def _pruefe_grenze(self, app) -> None:
        """Kein weiteres SAP-Fenster öffnen, wenn die Grenze erreicht ist.

        SAP erlaubt je Anmeldung nur eine begrenzte Zahl von Modi. Wer die
        aufbraucht, blockiert sich selbst und den Anwender. Lieber sauber
        melden als das letzte Fenster verbrauchen.
        """
        offen = zaehle_sessions(app)
        if offen >= self.max_sessions:
            raise SapUnavailable(
                f"In SAP sind bereits {offen} Fenster offen (Grenze "
                f"{self.max_sessions}), aber keines für {self.connection_name}. "
                f"Der Checker öffnet kein weiteres. Bitte ein SAP-Fenster "
                f"schließen oder sich in {self.connection_name} anmelden und "
                f"den Lauf fortsetzen.")

    def blockwechsel(self) -> None:
        """Nach jedem Block: SAP auf einen sauberen Stand bringen.

        Offene Dialoge wegräumen, zurück auf das Selektionsbild und die
        Zahl der offenen Fenster prüfen. So startet jeder Block unter
        denselben Bedingungen, statt sich über Stunden zu verzetteln.
        """
        if self.session is None:
            return
        try:
            from .popups import handle_popups

            geschlossen = handle_popups(self.session)
            if geschlossen:
                log.info("Blockwechsel: %d Dialog(e) geschlossen", geschlossen)
        except Exception:
            log.debug("Blockwechsel: Dialoge nicht prüfbar", exc_info=True)
        try:
            # Zurück auf das Einstiegsbild der Transaktion.
            self.session.FindById("wnd[0]/tbar[0]/okcd").Text = "/n"
            self.session.FindById("wnd[0]").SendVKey(0)
        except Exception:
            log.debug("Blockwechsel: Rücksprung nicht möglich", exc_info=True)
        try:
            offen = zaehle_sessions(self.session.Parent.Parent)
            if offen > self.max_sessions:
                log.warning("In SAP sind %d Fenster offen (Grenze %d) - "
                            "bitte nicht benötigte schließen",
                            offen, self.max_sessions)
        except Exception:
            log.debug("Blockwechsel: Fensterzahl unbekannt", exc_info=True)

    def close(self) -> None:
        """Aufräumen. Eine selbst geöffnete Session wird auch geschlossen.

        Sonst bleibt nach jedem Lauf ein SAP-Fenster stehen, und nach fünf
        Läufen ist die Grenze erreicht.
        """
        if self._selbst_geoeffnet and self.session is not None:
            try:
                verbindung = self.session.Parent
                verbindung.CloseSession(self.session.ID)
                log.info("Selbst geöffnete SAP-Session geschlossen")
            except Exception:
                log.debug("Session ließ sich nicht schließen", exc_info=True)
        self._selbst_geoeffnet = False
        self.session = None


def zaehle_sessions(app) -> int:
    """Wie viele SAP-Fenster (Modi) sind insgesamt offen?"""
    gesamt = 0
    try:
        for ci in range(app.Children.Count):
            gesamt += app.Children(ci).Children.Count
    except Exception:
        log.debug("Session-Zahl nicht ermittelbar", exc_info=True)
    return gesamt


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
