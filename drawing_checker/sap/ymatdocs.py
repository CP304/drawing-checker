"""Transaktionsablauf YMATDOCS: Report ausführen und ZIP-Paket herunterladen.

!!! PORTIERUNGSPUNKT (morgen): Die mit `# VBS:` markierten Stellen werden aus
dem .vbs-Mitschnitt der Transaktion übernommen. Der Mitschnitt liefert die
exakten Element-IDs (session.findById(...)-Pfade). Alles Übrige – Warten,
Fehlerklassifizierung, Download-Handling – ist hier bereits fertig.

Erwarteter Ablauf laut Prozess:
  1. /nYMATDOCS starten
  2. Materialnummer eintragen, ausführen
  3. Download des Dokumentpakets anstoßen -> SAP-Dateidialog
  4. Zielpfad setzen, speichern, ggf. "Datei ersetzen" bestätigen
  5. Warten, bis das ZIP vollständig geschrieben ist
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from .adapter import MaterialNotFound, SapUnavailable
from .session import find_element, wait_ready

log = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT_S = 180

# ---------------------------------------------------------------------------
# Element-IDs der Transaktion. Platzhalter, bis der .vbs-Mitschnitt vorliegt.
# Die IDs unten sind die üblichen Muster eines Selektionsbilds; sie werden
# beim Portieren durch die echten IDs aus dem .vbs ersetzt.
# ---------------------------------------------------------------------------
ID_OK_CODE = "wnd[0]/tbar[0]/okcd"
ID_MATERIAL_FIELD = "wnd[0]/usr/ctxtP_MATNR"          # VBS: echte Feld-ID einsetzen
ID_EXECUTE_BTN = "wnd[0]/tbar[1]/btn[8]"              # VBS: prüfen (F8 üblich)
ID_DOWNLOAD_BTN = "wnd[0]/tbar[1]/btn[13]"            # VBS: echten Button einsetzen
ID_FILEDLG_PATH = "wnd[1]/usr/ctxtDY_PATH"            # VBS: prüfen
ID_FILEDLG_NAME = "wnd[1]/usr/ctxtDY_FILENAME"        # VBS: prüfen
ID_FILEDLG_SAVE = "wnd[1]/tbar[0]/btn[0]"             # VBS: prüfen
ID_REPLACE_YES = "wnd[2]/usr/btnSPOP-OPTION1"         # "Ersetzen"-Dialog


def run_ymatdocs(session, material: str, target_dir: Path) -> Path:
    """Führt YMATDOCS für eine Materialnummer aus, liefert den ZIP-Pfad."""
    target_dir.mkdir(parents=True, exist_ok=True)
    zip_path = target_dir / f"{material}.zip"
    zip_path.unlink(missing_ok=True)

    _start_transaction(session)
    _enter_material_and_execute(session, material)
    _trigger_download(session, zip_path)
    _wait_for_file(zip_path, material)
    return zip_path


def _start_transaction(session) -> None:
    try:
        session.FindById(ID_OK_CODE).Text = "/nYMATDOCS"
        session.FindById("wnd[0]").SendVKey(0)
    except Exception as exc:
        raise SapUnavailable(f"Transaktionsstart fehlgeschlagen: {exc}") from exc
    wait_ready(session)
    _raise_on_error_status(session, context="Transaktionsstart")


def _enter_material_and_execute(session, material: str) -> None:
    field = find_element(session, ID_MATERIAL_FIELD)
    if field is None:
        raise SapUnavailable(
            f"Materialfeld {ID_MATERIAL_FIELD!r} nicht gefunden – Element-IDs "
            "aus dem .vbs-Mitschnitt eintragen (sap/ymatdocs.py)")
    field.Text = material
    # VBS: falls weitere Selektionsfelder gesetzt werden (Layout, Doku-Typen),
    # hier ergänzen.
    session.FindById(ID_EXECUTE_BTN).Press()
    wait_ready(session, timeout=120)

    status = _status_message(session)
    if status and _looks_like_not_found(status):
        raise MaterialNotFound(f"{material}: {status}")
    _raise_on_error_status(session, context=f"Ausführung für {material}")


def _trigger_download(session, zip_path: Path) -> None:
    btn = find_element(session, ID_DOWNLOAD_BTN)
    if btn is None:
        raise SapUnavailable(
            f"Download-Button {ID_DOWNLOAD_BTN!r} nicht gefunden – Element-IDs "
            "aus dem .vbs-Mitschnitt eintragen (sap/ymatdocs.py)")
    btn.Press()
    wait_ready(session)

    # SAP-Dateidialog: Pfad + Dateiname setzen.
    path_field = find_element(session, ID_FILEDLG_PATH)
    name_field = find_element(session, ID_FILEDLG_NAME)
    if name_field is None and path_field is None:
        raise SapUnavailable("Datei-Dialog nicht erkannt – IDs aus .vbs prüfen")
    if path_field is not None:
        path_field.Text = str(zip_path.parent)
    if name_field is not None:
        name_field.Text = zip_path.name
    session.FindById(ID_FILEDLG_SAVE).Press()
    wait_ready(session)

    replace = find_element(session, ID_REPLACE_YES)
    if replace is not None:
        replace.Press()
        wait_ready(session)


def _wait_for_file(zip_path: Path, material: str) -> None:
    """Wartet, bis das ZIP existiert und die Größe stabil ist."""
    deadline = time.time() + DOWNLOAD_TIMEOUT_S
    last_size = -1
    stable_since: float | None = None
    while time.time() < deadline:
        if zip_path.exists():
            size = zip_path.stat().st_size
            if size > 0 and size == last_size:
                if stable_since and time.time() - stable_since >= 1.5:
                    log.info("%s: ZIP vollständig (%d Bytes)", material, size)
                    return
                stable_since = stable_since or time.time()
            else:
                stable_since = None
            last_size = size
        time.sleep(0.5)
    raise SapUnavailable(
        f"{material}: Download nicht abgeschlossen (> {DOWNLOAD_TIMEOUT_S}s)")


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
        "not found", "does not exist", "no documents"))


def _raise_on_error_status(session, context: str) -> None:
    if _status_type(session) in ("E", "A"):
        msg = _status_message(session)
        if _looks_like_not_found(msg):
            raise MaterialNotFound(msg)
        raise SapUnavailable(f"{context}: SAP-Fehler: {msg}")
