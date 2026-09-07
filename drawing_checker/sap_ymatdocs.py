"""YMATDOCS beschaffen: Schnittstelle, echter Weg, Mock, Testsitzung.

Die Schnittstelle, die der Orchestrator sieht, und die drei Wege sie zu
erfuellen: echtes SAP, Ordner mit ZIPs, und eine nachgebaute Sitzung
fuer Tests und den Trockenlauf.
"""
from __future__ import annotations

# ======================================================================
# ymatdocs
# ======================================================================
# Transaktionsablauf YMATDOCS: Report ausführen und ZIP-Paket herunterladen.
#
# Der Ablauf wird NICHT fest programmiert, sondern aus dem .vbs-Mitschnitt der
# Transaktion importiert und abgespielt (siehe `vbs_parser.py`,
# `script_flow.py`). Damit entfällt das fehleranfällige Abtippen von
# Element-IDs, und ein abweichender Ablauf (zusätzliche Selektionsfelder,
# Layout-Auswahl, Zwischenbilder) funktioniert ohne Codeänderung.
#
# Ablauf je Materialnummer:
#   1. Ablauf laden (einmalig, aus `regeln/ymatdocs_flow.yaml` bzw. dem über
#      `--sap-flow` angegebenen Pfad).
#   2. Download-Überwachung starten (erwarteter Pfad + Ordner).
#   3. Schritte abspielen, dabei Popups automatisch behandeln.
#   4. Auf die fertige Datei warten und sie an den Zielort verschieben.
#
# Ohne importierten Ablauf greift der eingebaute Standardablauf (die früher
# hartcodierte Variante) – er dient nur als Notnagel und meldet klar, dass
# der Mitschnitt fehlt.



import logging
import shutil
from pathlib import Path

from .sap_sitzung import MaterialNotFound, SapUnavailable
from .sap_sitzung import DownloadWatcher, default_watch_dirs
from .sap_sitzung import handle_popups
from .sap_ablauf import Abgebrochen, FlowError, ScriptFlow, Step, play
from .sap_sitzung import find_element, wait_ready

log = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT_S = 180
FLOW_FILENAME = "ymatdocs_flow.yaml"

# Notnagel-Ablauf, falls kein Mitschnitt importiert wurde. Die IDs sind die
# üblichen Muster eines Selektionsbilds – sie stimmen fast sicher NICHT mit
# YMATDOCS überein, liefern aber eine verständliche Fehlermeldung.
FALLBACK_FLOW = ScriptFlow(
    name="ymatdocs-fallback",
    transaction="YMATDOCS",
    material_field="wnd[0]/usr/ctxtP_MATNR",
    steps=[
        Step("start_transaction", value="/nYMATDOCS",
             comment="Transaktionsstart"),
        Step("set_text", "wnd[0]/usr/ctxtP_MATNR", "{material}",
             comment="Materialnummer (Standardannahme)"),
        Step("send_vkey", "wnd[0]", 8, comment="Ausführen (F8)"),
        Step("press", "wnd[0]/tbar[1]/btn[13]", optional=True,
             comment="Download (Standardannahme)"),
        Step("set_text", "wnd[1]/usr/ctxtDY_PATH", "{target_dir}",
             optional=True),
        Step("set_text", "wnd[1]/usr/ctxtDY_FILENAME", "{filename}",
             optional=True),
        Step("press", "wnd[1]/tbar[0]/btn[0]", optional=True),
    ],
    download_step_index=3,
    notes="Eingebauter Notnagel – bitte den .vbs-Mitschnitt importieren.",
)

_flow_cache: dict[str, ScriptFlow] = {}


def flow_search_paths() -> list[Path]:
    """Orte, an denen der importierte Ablauf gesucht wird."""
    from .regeln import rules_dirs

    paths = [d / FLOW_FILENAME for d in rules_dirs()]
    paths.append(Path.cwd() / FLOW_FILENAME)
    return paths


def load_flow(explicit: Path | None = None) -> tuple[ScriptFlow, Path | None]:
    """Lädt den Ablauf; liefert (Ablauf, Quelle) – Quelle None = Notnagel."""
    candidates = [explicit] if explicit else flow_search_paths()
    for path in candidates:
        if path and Path(path).is_file():
            key = str(path)
            if key not in _flow_cache:
                _flow_cache[key] = ScriptFlow.load(Path(path))
                log.info("SAP-Ablauf geladen: %s (%d Schritte)",
                         path, len(_flow_cache[key].steps))
            return _flow_cache[key], Path(path)
    return FALLBACK_FLOW, None


def run_ymatdocs(session, material: str, target_dir: Path, *,
                 flow_path: Path | None = None,
                 watch_dirs: list[Path] | None = None,
                 on_step=None,
                 timeout_s: float = DOWNLOAD_TIMEOUT_S,
                 abbruch=None) -> Path:
    """Führt YMATDOCS für eine Materialnummer aus, liefert den ZIP-Pfad.

    abbruch: Funktion ohne Argumente; liefert sie True, wird der Ablauf
    beim nächsten Schritt bzw. beim Warten auf den Download abgebrochen.
    Damit wirkt der Abbrechen-Knopf der GUI sofort und nicht erst nach
    dem Zeitablauf des Downloads.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    flow, source = load_flow(flow_path)
    if source is None:
        log.warning("Kein importierter SAP-Ablauf gefunden – Notnagel aktiv. "
                    "Mitschnitt mit --sap-import-vbs einlesen!")

    filename = f"{_safe(material)}.zip"
    expected = target_dir / filename
    context = {
        "material": material,
        "target_dir": str(target_dir),
        "filename": filename,
        "target_path": str(expected),
    }

    watcher = DownloadWatcher(
        expected=expected,
        watch_dirs=list(watch_dirs) if watch_dirs is not None
        else default_watch_dirs(),
        timeout_s=timeout_s)
    watcher.start()

    try:
        play(session, flow, context,
             wait_ready=lambda s: wait_ready(s, timeout=120),
             on_step=on_step,
             popup_handler=_popup_handler,
             abbruch=abbruch)
    except FlowError as exc:
        _raise_flow_error(session, material, exc, source)

    status = _status_message(session)
    if status and _looks_like_not_found(status):
        raise MaterialNotFound(f"{material}: {status}")
    _raise_on_error_status(session, context=f"Ausführung für {material}")

    try:
        downloaded = watcher.wait(abbruch=abbruch)
    except TimeoutError as exc:
        if abbruch is not None and abbruch():
            raise Abgebrochen(f"{material}: vom Anwender abgebrochen") from exc
        if status:
            raise MaterialNotFound(f"{material}: kein Paket ({status})") from exc
        raise SapUnavailable(str(exc)) from exc

    if downloaded != expected:
        log.info("Download lag unter %s – wird nach %s verschoben",
                 downloaded, expected)
        shutil.move(str(downloaded), str(expected))
    return expected


def _popup_handler(session, step) -> int:
    """Dialoge abräumen – außer dem Fenster, das der Schritt selbst bedient.

    Ohne diese Ausnahme würde der Automat den Speichern-Dialog des
    Downloads bestätigen, bevor Zielordner und Dateiname eingetragen sind.
    """
    return handle_popups(session, skip_windows=_step_windows(step))


def _step_windows(step) -> set[str]:
    element = getattr(step, "element", "") or ""
    if element.startswith("wnd["):
        return {element.split("/", 1)[0]}
    return set()


def _raise_flow_error(session, material: str, exc: FlowError,
                      source: Path | None) -> None:
    """Ordnet einen Ablauffehler fachlich oder technisch ein."""
    status = _status_message(session)
    if status and _looks_like_not_found(status):
        raise MaterialNotFound(f"{material}: {status}") from exc
    where = f"aus {source.name}" if source else "aus dem Notnagel-Ablauf"
    hint = ""
    if source is None:
        hint = (" – es ist kein .vbs-Mitschnitt importiert. "
                "Mit `drawing-checker --sap-import-vbs <datei.vbs>` einlesen.")
    raise SapUnavailable(f"{material}: {exc} ({where}){hint}") from exc


def _safe(material: str) -> str:
    import re

    return re.sub(r"[^\w.-]", "_", material.strip()) or "unbenannt"


# ------------------------------------------------------------------ Status
def _status_message(session) -> str:
    sbar = find_element(session, "wnd[0]/sbar")
    try:
        return (sbar.Text or "").strip() if sbar is not None else ""
    except Exception:
        return ""


def _status_type(session) -> str:
    sbar = find_element(session, "wnd[0]/sbar")
    try:
        return (sbar.MessageType or "") if sbar is not None else ""
    except Exception:
        return ""


def _looks_like_not_found(status: str) -> bool:
    s = status.lower()
    return any(k in s for k in (
        "nicht vorhanden", "existiert nicht", "keine dokumente", "nicht gefunden",
        "kein dokument", "keine daten", "no documents", "not found",
        "does not exist", "no data"))


def _raise_on_error_status(session, context: str) -> None:
    if _status_type(session) in ("E", "A"):
        msg = _status_message(session)
        if _looks_like_not_found(msg):
            raise MaterialNotFound(msg)
        raise SapUnavailable(f"{context}: SAP-Fehler: {msg}")


# ======================================================================
# mock
# ======================================================================
# Mock-SAP-Adapter: liefert YMATDOCS-Pakete aus einem Ordner.
#
# Erwartet je Materialnummer eine Datei `<material>.zip` im Quellordner.
# Dient der Entwicklung ohne SAP und den End-to-End-Tests; optional lässt
# sich ein SAP-Absturz injizieren, um Watchdog/Retry-Pfade zu testen.



import shutil
import time
from pathlib import Path

from .sap_sitzung import MaterialNotFound, SapAdapter, SapUnavailable


class MockSapAdapter(SapAdapter):
    def __init__(self, source_dir: Path, latency_s: float = 0.0,
                 crash_on: set[str] | None = None):
        self.source_dir = Path(source_dir)
        self.latency_s = latency_s
        self.crash_on = crash_on or set()   # Materialien, die 1x "abstürzen"
        self._crashed: set[str] = set()
        self.ready = False

    def ensure_ready(self) -> None:
        if not self.source_dir.is_dir():
            raise SapUnavailable(f"Mock-Quellordner fehlt: {self.source_dir}")
        self.ready = True

    def fetch_package(self, material: str, target_dir: Path) -> Path:
        if not self.ready:
            raise SapUnavailable("Mock-Adapter nicht verbunden (ensure_ready fehlt)")
        if material in self.crash_on and material not in self._crashed:
            # Simulierter Absturz: genau einmal, danach klappt der Retry.
            self._crashed.add(material)
            self.ready = False
            raise SapUnavailable(f"Simulierter SAP-Absturz bei {material}")
        if self.latency_s:
            time.sleep(self.latency_s)
        src = self.source_dir / f"{material}.zip"
        if not src.exists():
            raise MaterialNotFound(
                f"{material}: kein Dokumentpaket vorhanden (Mock)")
        target_dir.mkdir(parents=True, exist_ok=True)
        dst = target_dir / src.name
        shutil.copy2(src, dst)
        return dst

    def close(self) -> None:
        self.ready = False


# ======================================================================
# fake_session
# ======================================================================
# Nachbau einer SAP-GUI-Scripting-Session für Tests und Trockenläufe.
#
# Bildet die Teile der COM-API nach, die der Adapter nutzt (FindById, Text,
# Press, SendVKey, Busy, sbar …). Damit lässt sich der komplette Ablauf –
# Ablaufabspielen, Popup-Behandlung, Fehlerpfade, Download-Erkennung – ohne
# SAP-Installation prüfen. Wird ausschließlich in Tests und im Trockenlauf
# (`--sap-dry-run`) verwendet.



from pathlib import Path


class FakeElement:
    def __init__(self, session: "FakeSession", element_id: str,
                 kind: str = "generic"):
        self.session = session
        self.Id = element_id
        self.kind = kind
        self._text = ""
        self.Selected = False
        self.Key = ""
        self.CaretPosition = 0
        self.SelectedNode = ""

    # --- Eigenschaften -----------------------------------------------------
    @property
    def Text(self) -> str:
        return self._text

    @Text.setter
    def Text(self, value: str) -> None:
        self._text = value
        self.session.log.append(("set_text", self.Id, value))

    # --- Methoden ----------------------------------------------------------
    def Press(self) -> None:
        self.session.log.append(("press", self.Id, None))
        self.session._handle_press(self.Id)

    def Select(self) -> None:
        self.session.log.append(("select", self.Id, None))
        self.session._close_popup(self.Id)

    def SetFocus(self) -> None:
        self.session.log.append(("set_focus", self.Id, None))

    def Maximize(self) -> None:
        self.session.log.append(("maximize", self.Id, None))

    def SendVKey(self, key: int) -> None:
        self.session.log.append(("send_vkey", self.Id, key))
        self.session._handle_vkey(key)

    def DoubleClickNode(self, node: str) -> None:
        self.session.log.append(("double_click_node", self.Id, node))

    def __getattr__(self, name: str):
        """Unbekannte Scripting-Methoden generisch annehmen.

        Echte Grid- und Baum-Steuerelemente haben Dutzende Methoden
        (pressToolbarButton, setCurrentCell, selectItem …). Die Simulation
        nimmt jede davon an, protokolliert sie und löst – falls sie als
        Download-Auslöser konfiguriert ist – den simulierten Download aus.
        """
        if name.startswith("_"):
            raise AttributeError(name)

        def _generic(*args):
            self.session.log.append((f"call:{name}", self.Id, args))
            self.session._fire(self.Id, name)
            self.session._close_popup(self.Id)
            return None

        return _generic


class FakeStatusBar(FakeElement):
    def __init__(self, session: "FakeSession"):
        super().__init__(session, "wnd[0]/sbar", "statusbar")
        self.MessageType = ""

    @property
    def Text(self) -> str:
        return self._text

    @Text.setter
    def Text(self, value: str) -> None:
        self._text = value


class FakeInfo:
    def __init__(self, system: str = "P11"):
        self.SystemName = system
        self.Client = "100"
        self.User = "TESTUSER"
        self.Transaction = ""


class FakeSession:
    """Minimale SAP-Session für Tests.

    Parameter:
      download_target  Datei, die beim Auslösen des Downloads entsteht.
      download_bytes   Inhalt dieser Datei.
      popup_after      Element-ID, nach deren Press ein Popup erscheint.
      fail_on          Element-ID, deren Zugriff einen COM-Fehler auslöst.
      missing          Element-IDs, die es nicht gibt.
      status           (Text, Typ) für die Statuszeile nach dem Ausführen.
    """

    def __init__(self, *, download_target: Path | None = None,
                 download_bytes: bytes = b"PK\x03\x04 fake zip",
                 download_trigger: str | None = None,
                 popup_after: str | None = None,
                 fail_on: str | None = None,
                 missing: set[str] | None = None,
                 status: tuple[str, str] = ("", ""),
                 busy_cycles: int = 0):
        self.log: list[tuple[str, str, object]] = []
        self.elements: dict[str, FakeElement] = {}
        self.download_target = Path(download_target) if download_target else None
        self.download_bytes = download_bytes
        self.download_trigger = download_trigger
        self.popup_after = popup_after
        self.fail_on = fail_on
        self.missing = set(missing or ())
        self.open_popups: set[str] = set()
        self.alive = True
        self._busy_cycles = busy_cycles
        self.Info = FakeInfo()
        self.sbar = FakeStatusBar(self)
        self.sbar.Text, self.sbar.MessageType = status
        self.elements["wnd[0]/sbar"] = self.sbar

    # --- COM-Oberfläche ----------------------------------------------------
    @property
    def Busy(self) -> bool:
        if not self.alive:
            raise RuntimeError("Session ist tot (simulierter Absturz)")
        if self._busy_cycles > 0:
            self._busy_cycles -= 1
            return True
        return False

    def FindById(self, element_id: str, raise_missing: bool = True):
        if not self.alive:
            raise RuntimeError("Session ist tot (simulierter Absturz)")
        if self.fail_on and element_id == self.fail_on:
            raise RuntimeError(f"COM-Fehler an {element_id}")
        if element_id in self.missing:
            if raise_missing:
                raise RuntimeError(f"Element {element_id} nicht gefunden")
            return None
        # Popup-Elemente gibt es nur, solange das Popup offen ist.
        if element_id.startswith(("wnd[1]", "wnd[2]")):
            window = element_id.split("/")[0]
            if window not in self.open_popups:
                if raise_missing:
                    raise RuntimeError(f"Fenster {window} ist nicht offen")
                return None
        if element_id not in self.elements:
            self.elements[element_id] = FakeElement(self, element_id)
        return self.elements[element_id]

    # --- Simuliertes Verhalten --------------------------------------------
    def _handle_press(self, element_id: str) -> None:
        self._fire(element_id)
        self._close_popup(element_id)

    def _handle_vkey(self, key: int) -> None:
        self._fire(f"vkey:{key}")

    def _matches(self, trigger: str | None, element_id: str,
                 method: str | None) -> bool:
        """Passt der konfigurierte Auslöser auf diese Aktion?

        Erlaubt sind die Element-ID selbst, `ID:methode` und der reine
        Methodenname (z. B. "pressToolbarButton") sowie `vkey:<n>`.
        """
        if not trigger:
            return False
        if trigger == element_id:
            return True
        if method and trigger in (f"{element_id}:{method}", method):
            return True
        return False

    def _fire(self, element_id: str, method: str | None = None) -> None:
        """Simulierte Nebenwirkungen einer Aktion (Popup, Download).

        Wird von Press, SendVKey und jeder generischen Scripting-Methode
        aufgerufen, damit auch ALV-Grid-Auslöser wie
        `pressToolbarButton "DOWNLOAD"` einen Datei-Dialog öffnen.
        """
        if self._matches(self.popup_after, element_id, method):
            self.open_popups.add("wnd[1]")
        if self._matches(self.download_trigger, element_id, method):
            self._write_download()

    def _close_popup(self, element_id: str) -> None:
        if element_id.startswith("wnd[1]"):
            self.open_popups.discard("wnd[1]")
        elif element_id.startswith("wnd[2]"):
            self.open_popups.discard("wnd[2]")

    def _write_download(self) -> None:
        if self.download_target is None:
            return
        self.download_target.parent.mkdir(parents=True, exist_ok=True)
        self.download_target.write_bytes(self.download_bytes)

    def crash(self) -> None:
        """Simuliert einen SAP-Absturz: alle weiteren Zugriffe scheitern."""
        self.alive = False

    def open_popup(self, window: str = "wnd[1]") -> None:
        self.open_popups.add(window)

    # --- Auswertung für Tests ---------------------------------------------
    def actions(self) -> list[str]:
        return [a for a, _e, _v in self.log]

    def texts_of(self, element_id: str) -> list[object]:
        return [v for a, e, v in self.log if a == "set_text" and e == element_id]
