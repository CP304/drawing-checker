"""Diagnose-Werkzeuge für den SAP-Durchstich.

Wenn morgen ein Schritt nicht greift, entscheidet die Diagnose darüber, wie
schnell die Ursache gefunden ist:

  dump_screen     Elementbaum des aktuellen Bildes (welche Felder gibt es,
                  wie heißen sie?) – der Ersatz für „raten".
  save_screenshot Bildschirmfoto des SAP-Fensters zum Fehlerzeitpunkt.
  describe_session Verbindungsdaten (System, Mandant, Benutzer, Transaktion).
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

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
