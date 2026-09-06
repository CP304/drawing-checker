"""Behandlung unerwarteter SAP-Dialoge.

In einem Dauerlauf tauchen Popups auf, die im Mitschnitt nicht vorkamen:
Mehrfachanmeldung, „Datei existiert bereits", Informationsmeldungen,
Druckdialoge. Ohne Behandlung blockieren sie den gesamten Lauf.

Strategie: bekannte Dialoge anhand ihres Titels/Textes automatisch
beantworten, unbekannte protokollieren und mit Enter bzw. Abbrechen
schließen – der Lauf darf nie an einem Dialog hängen bleiben.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

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
