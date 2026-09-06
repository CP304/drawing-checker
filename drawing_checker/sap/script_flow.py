"""Aufgezeichneter SAP-Ablauf als abspielbare Schrittfolge.

Statt den Transaktionsablauf fest zu programmieren, spielt der Adapter die
Schritte ab, die aus dem .vbs-Mitschnitt der Transaktion stammen. Vorteile:

  * Kein manuelles Übertragen von Element-IDs (fehleranfällig).
  * Der Ablauf darf beliebig aussehen (mehrere Selektionsfelder, Layout-
    Auswahl, Zwischenbilder) – abgespielt wird, was aufgezeichnet wurde.
  * Platzhalter erlauben es, dieselbe Aufzeichnung für jede Materialnummer
    zu verwenden.

Platzhalter in Werten:
  {material}     Materialnummer der aktuellen Zeile
  {target_dir}   Zielordner für den Download
  {filename}     Dateiname des ZIP (z. B. "10473215.zip")
  {target_path}  Vollständiger Pfad (Ordner + Dateiname)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)


@dataclass
class Step:
    """Eine Aktion im aufgezeichneten Ablauf.

    Neben den benannten Aktionen (set_text, press …) gibt es zwei
    generische Formen, mit denen JEDE Scripting-Anweisung abspielbar ist:

      action: "call"      method + args  -> element.<method>(*args)
      action: "set_prop"  member + value -> element.<member> = value

    Damit funktionieren auch ALV-Grid- und Baum-Methoden
    (pressToolbarButton, setCurrentCell, selectItem …), ohne dass der
    Player sie einzeln kennen muss.
    """

    action: str                 # set_text | press | send_vkey | call |
                                # set_prop | start_transaction | sleep | ...
    element: str = ""           # findById-Pfad, leer bei Sonderaktionen
    value: Any = None           # Text, VKey-Nummer, Index …
    optional: bool = False      # fehlendes Element ist kein Fehler
    comment: str = ""           # Herkunft/Erläuterung (aus dem .vbs)
    method: str = ""            # bei action="call"
    member: str = ""            # bei action="set_prop"
    args: list = field(default_factory=list)   # Argumente für "call"

    def resolve(self, context: dict[str, str]) -> Any:
        """Platzhalter im Wert ersetzen."""
        return _fill(self.value, context)

    def resolved_args(self, context: dict[str, str]) -> list:
        return [_fill(a, context) for a in self.args]


def _fill(value: Any, context: dict[str, str]) -> Any:
    if isinstance(value, str):
        try:
            return value.format(**context)
        except (KeyError, IndexError, ValueError):
            return value
    return value


@dataclass
class ScriptFlow:
    """Kompletter Ablauf einer Transaktion."""

    name: str = "ymatdocs"
    transaction: str = ""
    steps: list[Step] = field(default_factory=list)
    # Element-IDs, die für die Automatisierung besonders wichtig sind.
    material_field: str = ""
    download_step_index: int | None = None
    notes: str = ""

    # ------------------------------------------------------------ Persistenz
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "transaction": self.transaction,
            "material_field": self.material_field,
            "download_step_index": self.download_step_index,
            "notes": self.notes,
            "steps": [
                {k: v for k, v in {
                    "action": s.action,
                    "element": s.element,
                    "method": s.method,
                    "member": s.member,
                    "value": s.value,
                    "args": list(s.args) or None,
                    "optional": s.optional or None,
                    "comment": s.comment or None,
                }.items() if v is not None and v != ""}
                for s in self.steps
            ],
        }

    def save(self, path: Path) -> None:
        path.write_text(
            "# Aufgezeichneter SAP-Ablauf (aus .vbs importiert).\n"
            "# Platzhalter: {material}, {target_dir}, {filename}, {target_path}\n"
            "# Schritte dürfen von Hand nachgebessert werden.\n\n"
            + yaml.safe_dump(self.to_dict(), allow_unicode=True,
                             sort_keys=False),
            encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ScriptFlow":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        steps = [
            Step(action=s["action"], element=s.get("element", ""),
                 value=s.get("value"), optional=bool(s.get("optional", False)),
                 comment=s.get("comment", ""), method=s.get("method", ""),
                 member=s.get("member", ""), args=list(s.get("args") or []))
            for s in data.get("steps", [])
        ]
        return cls(
            name=data.get("name", "ymatdocs"),
            transaction=data.get("transaction", ""),
            steps=steps,
            material_field=data.get("material_field", ""),
            download_step_index=data.get("download_step_index"),
            notes=data.get("notes", ""),
        )


# ---------------------------------------------------------------- Abspielen
class FlowError(Exception):
    """Ein Schritt konnte nicht ausgeführt werden."""

    def __init__(self, message: str, step: Step, index: int):
        super().__init__(message)
        self.step = step
        self.index = index


class Abgebrochen(Exception):
    """Der Anwender hat den Lauf abgebrochen."""


def play(session, flow: ScriptFlow, context: dict[str, str], *,
         wait_ready=None, on_step=None, popup_handler=None,
         stop_after: int | None = None, abbruch=None) -> None:
    """Spielt den Ablauf auf einer SAP-Session ab.

    wait_ready:    Funktion, die auf ein antwortbereites SAP wartet.
    on_step:       Callback(index, step, resolved) – für Diagnose/Protokoll.
    popup_handler: Funktion(session, step), die unerwartete Dialoge
                   wegräumt; wird vor jedem Schritt aufgerufen. Der
                   anstehende Schritt wird mitgegeben, damit das Fenster,
                   das dieser Schritt bedient, stehen bleibt.
    stop_after:    Nur die ersten n Schritte ausführen (Schrittbetrieb).
    abbruch:       Funktion ohne Argumente; liefert sie True, wird vor dem
                   nächsten Schritt abgebrochen (Knopf in der GUI).
    """
    for index, step in enumerate(flow.steps):
        if stop_after is not None and index >= stop_after:
            return
        if abbruch is not None and abbruch():
            raise Abgebrochen(
                f"Abgebrochen vor Schritt {index + 1} ({step.action})")
        resolved = step.resolve(context)
        if on_step:
            on_step(index, step, resolved)
        if popup_handler:
            popup_handler(session, step)
        try:
            _execute(session, step, resolved, context)
        except FlowError:
            raise
        except Exception as exc:
            if step.optional:
                log.info("Optionaler Schritt %d (%s) übersprungen: %s",
                         index, step.action, exc)
                continue
            raise FlowError(
                f"Schritt {index + 1} ({step.action} {step.element}) "
                f"fehlgeschlagen: {exc}", step, index) from exc
        if wait_ready:
            wait_ready(session)


def _execute(session, step: Step, value: Any,
             context: dict[str, str] | None = None) -> None:
    action = step.action
    if action == "sleep":
        time.sleep(float(value or 0.5))
        return
    if action == "start_transaction":
        session.FindById("wnd[0]/tbar[0]/okcd").Text = value
        session.FindById("wnd[0]").SendVKey(0)
        return

    element = None
    if step.element:
        element = _find(session, step.element)
        if element is None:
            if step.optional:
                return
            raise FlowError(
                f"Element {step.element!r} nicht gefunden", step, -1)

    if action == "set_text":
        element.Text = "" if value is None else str(value)
    elif action == "press":
        element.Press()
    elif action == "select":
        element.Select()
    elif action == "set_focus":
        element.SetFocus()
    elif action == "set_checked":
        element.Selected = bool(value)
    elif action == "set_key":
        element.Key = str(value)
    elif action == "send_vkey":
        target = element if element is not None else _find(session, "wnd[0]")
        target.SendVKey(int(value))
    elif action == "maximize":
        (element or _find(session, "wnd[0]")).Maximize()
    elif action == "select_node":
        element.SelectedNode = str(value)
    elif action == "double_click_node":
        element.DoubleClickNode(str(value))
    elif action == "set_caret":
        element.CaretPosition = int(value)
    elif action == "call":
        # Generisch: beliebige Scripting-Methode mit Argumenten
        method = _resolve_member(element, step.method)
        if method is None:
            raise FlowError(
                f"Methode {step.method!r} an {step.element} nicht vorhanden",
                step, -1)
        method(*step.resolved_args(context or {}))
    elif action == "set_prop":
        member = _actual_member_name(element, step.member)
        if member is None:
            raise FlowError(
                f"Eigenschaft {step.member!r} an {step.element} nicht vorhanden",
                step, -1)
        setattr(element, member, value)
    else:
        raise FlowError(f"Unbekannte Aktion {action!r}", step, -1)


def _actual_member_name(element, name: str) -> str | None:
    """COM ist case-insensitiv, Python nicht – passende Schreibweise finden."""
    if hasattr(element, name):
        return name
    lowered = name.lower()
    for candidate in dir(element):
        if candidate.lower() == lowered:
            return candidate
    # Bei echten COM-Objekten listet dir() nichts Brauchbares: Großschreibung
    # der ersten Buchstaben ist die übliche Form (pressToolbarButton ->
    # PressToolbarButton).
    return name[0].upper() + name[1:] if name else None


def _resolve_member(element, name: str):
    actual = _actual_member_name(element, name)
    if actual is None:
        return None
    member = getattr(element, actual, None)
    return member if callable(member) else None


def _find(session, element_id: str):
    try:
        return session.FindById(element_id, False)
    except TypeError:
        # Manche COM-Wrapper kennen den zweiten Parameter nicht.
        try:
            return session.FindById(element_id)
        except Exception:
            return None
    except Exception:
        return None
