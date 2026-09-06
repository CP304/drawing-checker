"""Watchdog: erkennt SAP-Abstürze und startet P11 automatisch neu.

Ablauf bei recover():
  1. SAP-Prozesse sauber beenden (nur SAP-eigene Prozesse).
  2. saplogon.exe starten und auf die Scripting-Engine warten.
  3. Verbindung öffnen; Login übernimmt SSO oder hinterlegte Credentials
     (Windows Credential Manager, niemals Klartext auf Platte).
  4. Exponentielles Backoff über mehrere Versuche.
"""
from __future__ import annotations

import logging
import os
import subprocess
import time

from .adapter import SapUnavailable

log = logging.getLogger(__name__)

SAP_PROCESSES = ["saplogon.exe", "sapgui.exe", "SAPgui.exe"]
DEFAULT_SAPLOGON = r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe"
CREDENTIAL_TARGET = "drawing-checker/P11"  # Eintrag im Windows Credential Manager

MAX_ATTEMPTS = 4
BACKOFF_BASE_S = 5


class SapWatchdog:
    def __init__(self, connection_name: str, saplogon_path: str | None = None):
        self.connection_name = connection_name
        self.saplogon_path = saplogon_path or os.environ.get(
            "SAPLOGON_PATH", DEFAULT_SAPLOGON)

    # -------------------------------------------------------------- Recovery
    def recover(self) -> None:
        """Kompletter Neustart-Zyklus mit Backoff. Wirft SapUnavailable,
        wenn alle Versuche scheitern."""
        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                log.warning("SAP-Recovery, Versuch %d/%d", attempt, MAX_ATTEMPTS)
                self.kill_sap()
                self.start_sapgui()
                return
            except Exception as exc:
                last_error = exc
                wait = BACKOFF_BASE_S * (2 ** (attempt - 1))
                log.error("Recovery-Versuch %d fehlgeschlagen: %s – warte %ds",
                          attempt, exc, wait)
                time.sleep(wait)
        raise SapUnavailable(
            f"SAP-Neustart nach {MAX_ATTEMPTS} Versuchen fehlgeschlagen: {last_error}")

    def kill_sap(self) -> None:
        for proc in SAP_PROCESSES:
            subprocess.run(
                ["taskkill", "/F", "/IM", proc],
                capture_output=True, check=False,
            )
        time.sleep(2)

    def start_sapgui(self):
        """Startet saplogon.exe und liefert die Scripting-Engine."""
        try:
            import win32com.client
        except ImportError as exc:  # pragma: no cover
            raise SapUnavailable("pywin32 fehlt") from exc

        if not os.path.exists(self.saplogon_path):
            raise SapUnavailable(
                f"saplogon.exe nicht gefunden: {self.saplogon_path} "
                "(SAPLOGON_PATH setzen)")
        subprocess.Popen([self.saplogon_path])

        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                sapgui = win32com.client.GetObject("SAPGUI")
                return sapgui.GetScriptingEngine
            except Exception:
                time.sleep(1.5)
        raise SapUnavailable("SAP GUI startet, aber Scripting-Engine kommt nicht hoch")

    # ----------------------------------------------------------------- Login
    def login_if_needed(self, session) -> None:
        """Füllt den Login-Screen, falls er erscheint (kein SSO).

        Credentials kommen aus dem Windows Credential Manager
        (Eintrag 'drawing-checker/P11'); die GUI legt sie bei der ersten
        Nutzung dort ab. Bei SSO erscheint kein Login-Screen -> no-op.
        """
        from .session import find_element, wait_ready

        wait_ready(session)
        user_field = find_element(session, "wnd[0]/usr/txtRSYST-BNAME")
        if user_field is None:
            return  # SSO oder bereits angemeldet
        user, password = self._load_credentials()
        if not user:
            raise SapUnavailable(
                "SAP-Login erforderlich, aber keine Credentials hinterlegt "
                "(GUI: Einstellungen → SAP-Anmeldung)")
        user_field.Text = user
        session.FindById("wnd[0]/usr/pwdRSYST-BCODE").Text = password
        session.FindById("wnd[0]").SendVKey(0)  # Enter
        wait_ready(session)
        # Mehrfachanmeldungs-Dialog: bestehende Anmeldung übernehmen.
        multi = find_element(session, "wnd[1]/usr/radMULTI_LOGON_OPT2")
        if multi is not None:
            multi.Select()
            session.FindById("wnd[1]/tbar[0]/btn[0]").Press()
            wait_ready(session)

    @staticmethod
    def _load_credentials() -> tuple[str, str]:
        try:
            import win32cred  # pragma: no cover - nur Windows

            cred = win32cred.CredRead(CREDENTIAL_TARGET,
                                      win32cred.CRED_TYPE_GENERIC)
            return cred["UserName"], cred["CredentialBlob"].decode("utf-16-le")
        except Exception:
            return "", ""

    @staticmethod
    def store_credentials(user: str, password: str) -> None:
        import win32cred  # pragma: no cover - nur Windows

        win32cred.CredWrite({
            "Type": win32cred.CRED_TYPE_GENERIC,
            "TargetName": CREDENTIAL_TARGET,
            "UserName": user,
            "CredentialBlob": password.encode("utf-16-le"),
            "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
        }, 0)
