"""SAP-Sitzung: verbinden, Fenster huetten, Popups, Download, Diagnose.

Alles, was mit der laufenden SAP GUI zu tun hat - inklusive der Schranke
von fuenf Fenstern und dem Waechter, der SAP nach einem Absturz wieder
hochbringt.
"""
from __future__ import annotations

# ======================================================================
# adapter
# ======================================================================
# Adapter-Interface zur SAP-Beschaffung der YMATDOCS-Pakete.
#
# Der Orchestrator kennt nur dieses Interface. Implementierungen:
#   * SapGuiAdapter (sap/session.py): echtes SAP GUI Scripting (nur Windows).
#   * MockSapAdapter (sap/mock.py): liefert ZIPs aus einem Ordner – für
#     Entwicklung/Tests ohne SAP und für die Mockdaten-Läufe.



import abc
from pathlib import Path


class SapUnavailable(Exception):
    """SAP-Session tot/abgestürzt: Watchdog-Fall, Job wird neu eingereiht."""


class MaterialNotFound(Exception):
    """YMATDOCS kennt die Materialnummer nicht bzw. liefert kein Paket."""


class SapAdapter(abc.ABC):
    @abc.abstractmethod
    def ensure_ready(self) -> None:
        """Stellt eine nutzbare Session her (verbinden, ggf. neu starten)."""

    @abc.abstractmethod
    def fetch_package(self, material: str, target_dir: Path) -> Path:
        """Führt YMATDOCS für die Materialnummer aus und lädt das ZIP herunter.

        Rückgabe: Pfad des heruntergeladenen ZIP.
        Wirft MaterialNotFound (fachlich) oder SapUnavailable (technisch).
        """

    @abc.abstractmethod
    def close(self) -> None:
        """Ressourcen freigeben (Session NICHT zwingend beenden)."""


# ======================================================================
# session
# ======================================================================
# SAP GUI Scripting: Verbindung zu P11 und Ausführung von YMATDOCS.
#
# Nur unter Windows lauffähig (COM). Voraussetzungen:
#   * SAP GUI installiert, Scripting client- und serverseitig freigeschaltet
#     (sapgui/user_scripting = TRUE – ist laut Basis bereits aktiv).
#   * pywin32 installiert (pip install pywin32).
#
# Der konkrete Transaktionsablauf steckt in ymatdocs.py und wird aus dem
# .vbs-Mitschnitt der Transaktion portiert (Element-IDs 1:1 übernehmen).



import logging
import time
from pathlib import Path


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
        from .sap_ymatdocs import run_ymatdocs

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
        from .sap_ymatdocs import run_ymatdocs

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
            pass  # (im selben Modul)

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
            pass  # (im selben Modul)

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


# ======================================================================
# popups
# ======================================================================
# Behandlung unerwarteter SAP-Dialoge.
#
# In einem Dauerlauf tauchen Popups auf, die im Mitschnitt nicht vorkamen:
# Mehrfachanmeldung, „Datei existiert bereits", Informationsmeldungen,
# Druckdialoge. Ohne Behandlung blockieren sie den gesamten Lauf.
#
# Strategie: bekannte Dialoge anhand ihres Titels/Textes automatisch
# beantworten, unbekannte protokollieren und mit Enter bzw. Abbrechen
# schließen – der Lauf darf nie an einem Dialog hängen bleiben.



import logging
import re


# Dialoge, die bestätigt werden dürfen (Enter / „Ja" / „Ersetzen").
CONFIRM_PATTERNS = [
    re.compile(r"ersetzen|überschreiben|replace|overwrite", re.IGNORECASE),
    re.compile(r"wirklich|fortfahren|continue|proceed", re.IGNORECASE),
    re.compile(r"informationen?|hinweis|information", re.IGNORECASE),
]
# Dialoge, die abgebrochen werden müssen (nicht bestätigen!).
CANCEL_PATTERNS = [
    re.compile(r"drucken|print", re.IGNORECASE),
    re.compile(r"löschen|delete|verwerfen|discard", re.IGNORECASE),
]
# Mehrfachanmeldung: bestehende Sitzung fortsetzen (Option 1).
MULTI_LOGON = re.compile(r"mehrfachanmeldung|multiple\s+logon", re.IGNORECASE)

MAX_POPUP_ROUNDS = 5


def handle_popups(session, *, on_popup=None, skip_windows=()) -> int:
    """Räumt offene Modaldialoge ab. Liefert die Anzahl behandelter Popups.

    skip_windows: Fenster, die der Ablauf selbst bedient (z. B. der
    Datei-Dialog des Downloads). Sie dürfen NICHT weggeklickt werden –
    sonst schließt der Automat den Speichern-Dialog, bevor Pfad und
    Dateiname eingetragen sind.
    """
    handled = 0
    skip = set(skip_windows)
    for _round in range(MAX_POPUP_ROUNDS):
        window = _topmost_popup(session, skip)
        if window is None:
            break
        title, text = _popup_text(session, window)
        info = f"{title} {text}".strip()
        if on_popup:
            on_popup(window, info)

        if MULTI_LOGON.search(info):
            _select_multi_logon(session, window)
        elif any(p.search(info) for p in CANCEL_PATTERNS):
            log.warning("Dialog abgebrochen: %s", info[:120])
            _press_button(session, window, cancel=True)
        elif any(p.search(info) for p in CONFIRM_PATTERNS):
            log.info("Dialog bestätigt: %s", info[:120])
            _press_button(session, window, cancel=False)
        else:
            log.warning("Unbekannter Dialog, wird bestätigt: %s", info[:160])
            _press_button(session, window, cancel=False)
        handled += 1
    return handled


def _topmost_popup(session, skip: set[str] | None = None):
    for window in ("wnd[2]", "wnd[1]"):
        if skip and window in skip:
            continue
        try:
            element = session.FindById(window, False)
        except Exception:
            element = None
        if element is not None:
            return window
    return None


def _popup_text(session, window: str) -> tuple[str, str]:
    title = _safe_attr(session, window, "Text")
    parts: list[str] = []
    for candidate in (f"{window}/usr/txtMESSTXT1", f"{window}/usr/txtMESSTXT2",
                      f"{window}/usr/txtSPOP-TEXTLINE1",
                      f"{window}/usr/txtSPOP-TEXTLINE2"):
        value = _safe_attr(session, candidate, "Text")
        if value:
            parts.append(value)
    return title, " ".join(parts)


def _safe_attr(session, element_id: str, attribute: str) -> str:
    try:
        element = session.FindById(element_id, False)
        if element is None:
            return ""
        return str(getattr(element, attribute, "") or "")
    except Exception:
        return ""


def _select_multi_logon(session, window: str) -> None:
    """Bestehende Anmeldung fortsetzen statt neue Sitzung zu öffnen."""
    for option in (f"{window}/usr/radMULTI_LOGON_OPT2",
                   f"{window}/usr/radMULTI_LOGON_OPT1"):
        try:
            element = session.FindById(option, False)
            if element is not None:
                element.Select()
                break
        except Exception:
            continue
    _press_button(session, window, cancel=False)


def _press_button(session, window: str, *, cancel: bool) -> None:
    """Dialog schließen: erst über die Symbolleiste, sonst per Tastendruck."""
    button = "btn[12]" if cancel else "btn[0]"
    for element_id in (f"{window}/tbar[0]/{button}",
                       f"{window}/usr/btnSPOP-OPTION{'2' if cancel else '1'}"):
        try:
            element = session.FindById(element_id, False)
            if element is not None:
                element.Press()
                return
        except Exception:
            continue
    try:
        session.FindById(window).SendVKey(12 if cancel else 0)
    except Exception:
        log.error("Dialog %s ließ sich nicht schließen", window)


# ======================================================================
# download
# ======================================================================
# Erkennung der heruntergeladenen ZIP-Datei.
#
# Wohin YMATDOCS das Paket ablegt, ist bis zum Durchstich unbekannt. Deshalb
# werden mehrere Wege gleichzeitig überwacht:
#
#   1. der erwartete Zielpfad (aus dem Datei-Dialog),
#   2. der Zielordner insgesamt (falls SAP den Dateinamen selbst vergibt),
#   3. zusätzliche Ordner (Windows-Download, SAP-Arbeitsverzeichnis, Temp).
#
# Erkannt wird jede Datei, die nach dem Start des Downloads neu entstanden
# ist; gewartet wird, bis ihre Größe stabil ist (Schreibvorgang beendet).



import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_TIMEOUT_S = 180.0
STABLE_SECONDS = 1.5
POLL_INTERVAL_S = 0.4
# Endungen, die als Ergebnis in Frage kommen (SAP legt teils .zip.tmp an).
CANDIDATE_SUFFIXES = (".zip", ".sar", ".rar", ".7z")
TEMP_SUFFIXES = (".tmp", ".part", ".crdownload", ".filepart")


def default_watch_dirs() -> list[Path]:
    """Ordner, in denen ein Download landen könnte."""
    dirs: list[Path] = []
    home = Path.home()
    for candidate in (home / "Downloads", home / "Documents" / "SAP",
                      home / "SAP" / "SAP GUI", Path(os.environ.get("TEMP", ""))
                      if os.environ.get("TEMP") else None):
        if candidate and candidate.is_dir():
            dirs.append(candidate)
    return dirs


@dataclass
class DownloadWatcher:
    """Überwacht mehrere Ordner auf eine neu entstandene Archivdatei."""

    expected: Path | None = None
    watch_dirs: list[Path] = field(default_factory=list)
    timeout_s: float = DEFAULT_TIMEOUT_S
    _before: dict[Path, set[Path]] = field(default_factory=dict, init=False)
    _started: float = field(default=0.0, init=False)

    def start(self) -> None:
        """Ausgangszustand festhalten (vor dem Auslösen des Downloads)."""
        self._started = time.time()
        self._before = {}
        if self.expected is not None:
            # Eine alte Datei gleichen Namens darf nicht als Treffer gelten.
            try:
                self.expected.unlink(missing_ok=True)
            except OSError:
                log.warning("Alte Datei %s ließ sich nicht entfernen",
                            self.expected)
        for directory in self._all_dirs():
            self._before[directory] = set(_list_files(directory))

    def wait(self, abbruch=None) -> Path:
        """Wartet auf die fertige Datei und liefert ihren Pfad.

        Wirft TimeoutError, wenn nichts erscheint. `abbruch` ist eine
        Funktion ohne Argumente; liefert sie True, wird das Warten sofort
        beendet – sonst müsste der Anwender nach dem Abbrechen-Knopf noch
        bis zu drei Minuten auf den Zeitablauf warten.
        """
        deadline = time.time() + self.timeout_s
        stable_since: dict[Path, tuple[int, float]] = {}
        while time.time() < deadline:
            if abbruch is not None and abbruch():
                raise TimeoutError("Download vom Anwender abgebrochen")
            for candidate in self._new_files():
                size = _size(candidate)
                if size <= 0:
                    continue
                last = stable_since.get(candidate)
                if last is not None and last[0] == size:
                    if time.time() - last[1] >= STABLE_SECONDS:
                        log.info("Download erkannt: %s (%d Bytes)",
                                 candidate, size)
                        return candidate
                else:
                    stable_since[candidate] = (size, time.time())
            time.sleep(POLL_INTERVAL_S)
        raise TimeoutError(
            f"Kein Download erkannt (Zielpfad {self.expected}, überwacht: "
            f"{', '.join(str(d) for d in self._all_dirs()) or 'keine Ordner'})")

    # ------------------------------------------------------------- Intern
    def _all_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        if self.expected is not None:
            dirs.append(self.expected.parent)
        for d in self.watch_dirs:
            if d not in dirs:
                dirs.append(d)
        return [d for d in dirs if d.is_dir()]

    def _new_files(self) -> list[Path]:
        found: list[Path] = []
        if self.expected is not None and self.expected.exists():
            found.append(self.expected)
        for directory in self._all_dirs():
            before = self._before.get(directory, set())
            for path in _list_files(directory):
                if path in before or path in found:
                    continue
                if not _is_candidate(path):
                    continue
                if path.stat().st_mtime < self._started - 5:
                    continue      # älter als der Downloadstart
                found.append(path)
        return found


def _list_files(directory: Path) -> list[Path]:
    try:
        return [p for p in directory.iterdir() if p.is_file()]
    except OSError:
        return []


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return -1


def _is_candidate(path: Path) -> bool:
    name = path.name.lower()
    if name.endswith(TEMP_SUFFIXES):
        return False
    return name.endswith(CANDIDATE_SUFFIXES)


# ======================================================================
# watchdog
# ======================================================================
# Watchdog: erkennt SAP-Abstürze und startet P11 automatisch neu.
#
# Ablauf bei recover():
#   1. SAP-Prozesse sauber beenden (nur SAP-eigene Prozesse).
#   2. saplogon.exe starten und auf die Scripting-Engine warten.
#   3. Verbindung öffnen; Login übernimmt SSO oder hinterlegte Credentials
#      (Windows Credential Manager, niemals Klartext auf Platte).
#   4. Exponentielles Backoff über mehrere Versuche.



import logging
import os
import subprocess
import time



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
        pass  # (im selben Modul)

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


# ======================================================================
# diagnostics
# ======================================================================
# Diagnose-Werkzeuge für den SAP-Durchstich.
#
# Wenn morgen ein Schritt nicht greift, entscheidet die Diagnose darüber, wie
# schnell die Ursache gefunden ist:
#
#   dump_screen     Elementbaum des aktuellen Bildes (welche Felder gibt es,
#                   wie heißen sie?) – der Ersatz für „raten".
#   save_screenshot Bildschirmfoto des SAP-Fensters zum Fehlerzeitpunkt.
#   describe_session Verbindungsdaten (System, Mandant, Benutzer, Transaktion).



import logging
from pathlib import Path


MAX_DEPTH = 6
INTERESTING = ("txt", "ctxt", "btn", "chk", "rad", "cmb", "lbl", "tbl",
               "shell", "tabs", "sub", "usr", "ssub")


def describe_session(session) -> str:
    """Kurzinfo zur Verbindung – für Protokoll und Fehlermeldungen."""
    try:
        info = session.Info
        return (f"System {info.SystemName}, Mandant {info.Client}, "
                f"Benutzer {info.User}, Transaktion "
                f"{getattr(info, 'Transaction', '?')}")
    except Exception as exc:
        return f"Sessioninfo nicht lesbar: {exc}"


def dump_screen(session, root: str = "wnd[0]", max_depth: int = MAX_DEPTH
                ) -> str:
    """Elementbaum des aktuellen Bildes als Text.

    Zeigt Id, Typ, Beschriftung und Inhalt – daraus lassen sich die
    Element-IDs für den Ablauf ablesen, ohne ein neues .vbs aufzunehmen.
    """
    lines: list[str] = [f"Elementbaum ab {root}:"]
    try:
        element = session.FindById(root, False)
    except Exception as exc:
        return f"{root} nicht lesbar: {exc}"
    if element is None:
        return f"{root} nicht vorhanden"
    _walk(element, lines, depth=0, max_depth=max_depth)
    return "\n".join(lines)


def _walk(element, lines: list[str], depth: int, max_depth: int) -> None:
    if depth > max_depth:
        return
    try:
        element_id = str(getattr(element, "Id", "?"))
        kind = str(getattr(element, "Type", "?"))
        text = str(getattr(element, "Text", "") or "")
        tooltip = str(getattr(element, "Tooltip", "") or "")
    except Exception:
        return
    short = element_id.split("/")[-1] if "/" in element_id else element_id
    if depth == 0 or any(short.lower().startswith(p) for p in INTERESTING) \
            or kind.startswith("GuiButton"):
        label = f" „{text[:40]}“" if text else ""
        tip = f" [{tooltip[:30]}]" if tooltip and tooltip != text else ""
        lines.append(f"{'  ' * depth}{element_id}  ({kind}){label}{tip}")
    try:
        children = element.Children
        count = children.Count
    except Exception:
        return
    for i in range(count):
        try:
            _walk(children(i), lines, depth + 1, max_depth)
        except Exception:
            continue


def save_screenshot(session, path: Path) -> Path | None:
    """Bildschirmfoto des SAP-Fensters (HardCopy); None wenn nicht möglich."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        window = session.FindById("wnd[0]")
        window.HardCopy(str(path))
        if path.exists():
            return path
    except Exception as exc:
        log.debug("HardCopy nicht möglich: %s", exc)
    # Fallback: kompletter Bildschirm
    try:
        import mss

        with mss.mss() as sct:
            sct.shot(output=str(path))
        return path if path.exists() else None
    except Exception as exc:
        log.debug("Bildschirmfoto nicht möglich: %s", exc)
        return None


def diagnose_failure(session, material: str, out_dir: Path) -> Path:
    """Schreibt einen Diagnosebericht zum Fehlerzeitpunkt."""
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / f"sap_diagnose_{material}.txt"
    parts = [
        f"SAP-Diagnose für Materialnummer {material}",
        describe_session(session),
        "",
        dump_screen(session),
    ]
    for window in ("wnd[1]", "wnd[2]"):
        try:
            if session.FindById(window, False) is not None:
                parts += ["", f"Offener Dialog {window}:",
                          dump_screen(session, window, max_depth=4)]
        except Exception:
            pass
    report.write_text("\n".join(parts), encoding="utf-8")
    shot = save_screenshot(session, out_dir / f"sap_bild_{material}.png")
    if shot:
        parts.append(f"\nBildschirmfoto: {shot}")
    log.info("SAP-Diagnose geschrieben: %s", report)
    return report
