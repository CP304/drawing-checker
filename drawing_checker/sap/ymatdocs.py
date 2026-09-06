"""Transaktionsablauf YMATDOCS: Report ausführen und ZIP-Paket herunterladen.

Der Ablauf wird NICHT fest programmiert, sondern aus dem .vbs-Mitschnitt der
Transaktion importiert und abgespielt (siehe `vbs_parser.py`,
`script_flow.py`). Damit entfällt das fehleranfällige Abtippen von
Element-IDs, und ein abweichender Ablauf (zusätzliche Selektionsfelder,
Layout-Auswahl, Zwischenbilder) funktioniert ohne Codeänderung.

Ablauf je Materialnummer:
  1. Ablauf laden (einmalig, aus `regeln/ymatdocs_flow.yaml` bzw. dem über
     `--sap-flow` angegebenen Pfad).
  2. Download-Überwachung starten (erwarteter Pfad + Ordner).
  3. Schritte abspielen, dabei Popups automatisch behandeln.
  4. Auf die fertige Datei warten und sie an den Zielort verschieben.

Ohne importierten Ablauf greift der eingebaute Standardablauf (die früher
hartcodierte Variante) – er dient nur als Notnagel und meldet klar, dass
der Mitschnitt fehlt.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .adapter import MaterialNotFound, SapUnavailable
from .download import DownloadWatcher, default_watch_dirs
from .popups import handle_popups
from .script_flow import Abgebrochen, FlowError, ScriptFlow, Step, play
from .session import find_element, wait_ready

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
    from ..checks.base import rules_dirs

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
