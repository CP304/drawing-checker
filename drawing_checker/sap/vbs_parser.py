"""Import eines SAP-GUI-Skript-Mitschnitts (.vbs) als abspielbarer Ablauf.

Der Mitschnitt aus „Skript aufzeichnen und abspielen" sieht so aus:

    session.findById("wnd[0]/tbar[0]/okcd").text = "/nYMATDOCS"
    session.findById("wnd[0]").sendVKey 0
    session.findById("wnd[0]/usr/ctxtS_MATNR-LOW").text = "10473215"
    session.findById("wnd[0]").sendVKey 8
    session.findById("wnd[0]/tbar[1]/btn[13]").press

Der Parser übersetzt das in Schritte, erkennt automatisch

  * den Transaktionscode,
  * das Feld, in das die Materialnummer eingetragen wird,
  * Datei-Dialog-Felder (Pfad/Dateiname) für den Download,

und ersetzt die aufgezeichneten Werte durch Platzhalter. Damit ist der
Ablauf sofort für beliebige Materialnummern verwendbar.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from .script_flow import ScriptFlow, Step

log = logging.getLogger(__name__)

# session.findById("...").text = "wert"      (auch .Text, ohne Klammern)
RE_SET_PROP = re.compile(
    r'findById\(\s*"([^"]+)"\s*\)\s*\.\s*(\w+)\s*=\s*(.+?)\s*$',
    re.IGNORECASE)
# session.findById("...").press / .select / .setFocus / .maximize
RE_CALL = re.compile(
    r'findById\(\s*"([^"]+)"\s*\)\s*\.\s*(\w+)\s*(?:\(\s*\))?\s*$',
    re.IGNORECASE)
# session.findById("...").sendVKey 8   /  .selectNode "F00001"
RE_CALL_ARG = re.compile(
    r'findById\(\s*"([^"]+)"\s*\)\s*\.\s*(\w+)\s+(.+?)\s*$', re.IGNORECASE)

RE_TRANSACTION = re.compile(r'^/n?\s*(\w+)', re.IGNORECASE)
# Werte, die wie eine Materialnummer aussehen (6–18 Stellen, ggf. führende 0).
RE_MATERIAL_VALUE = re.compile(r"^\d{6,18}$")
RE_PATH_VALUE = re.compile(r"^[A-Za-z]:\\|^\\\\|/")

# Feld-IDs, die typischerweise Datei-Dialoge betreffen.
PATH_FIELD_HINTS = ("DY_PATH", "PATH", "VERZEICHNIS", "DIRECTORY")
NAME_FIELD_HINTS = ("DY_FILENAME", "FILENAME", "DATEINAME")

PROP_ACTIONS = {
    "text": "set_text",
    "caretposition": "set_caret",
    "selected": "set_checked",
    "key": "set_key",
    "selectednode": "select_node",
}
CALL_ACTIONS = {
    "press": "press",
    "select": "select",
    "setfocus": "set_focus",
    "maximize": "maximize",
    "sendvkey": "send_vkey",
    "selectnode": "select_node",
    "doubleclicknode": "double_click_node",
}
# Aktionen, die für den automatischen Ablauf irrelevant sind.
SKIP_ACTIONS = {"set_caret", "set_focus", "maximize"}
# Methoden, die einen Download auslösen können (für die Trigger-Erkennung).
DOWNLOAD_HINTS = re.compile(
    r"download|export|speichern|save|lokal|sichern|xxl|excel|zip",
    re.IGNORECASE)


def parse_vbs(path: Path | str, *, keep_cosmetic: bool = False) -> ScriptFlow:
    """Liest einen .vbs-Mitschnitt und liefert den Ablauf."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    flow = ScriptFlow(name=Path(path).stem)
    material_values: list[tuple[int, str, str]] = []   # (index, element, wert)

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("'") or line.lower().startswith("rem "):
            continue
        if "findbyid" not in line.lower():
            continue

        step = _parse_line(line)
        if step is None:
            log.debug("Zeile nicht interpretierbar: %s", line)
            continue
        if step.action in SKIP_ACTIONS and not keep_cosmetic:
            continue

        # Transaktionscode erkennen und als eigenen Schritt führen
        if step.action == "set_text" and step.element.endswith("okcd"):
            m = RE_TRANSACTION.match(str(step.value).strip())
            if m:
                flow.transaction = m.group(1).upper()
            flow.steps.append(Step("start_transaction",
                                   value=str(step.value).strip(),
                                   comment="Transaktionsstart"))
            continue
        # Das direkt folgende Enter gehört zum Transaktionsstart
        if (step.action == "send_vkey" and flow.steps
                and flow.steps[-1].action == "start_transaction"
                and str(step.value) == "0"):
            continue

        if step.action == "set_text" and isinstance(step.value, str):
            value = step.value
            if RE_MATERIAL_VALUE.match(value):
                material_values.append((len(flow.steps), step.element, value))
            elif _is_path_field(step.element) or RE_PATH_VALUE.match(value):
                step.value = ("{target_dir}" if _is_path_field(step.element)
                              else "{target_path}")
                step.comment = step.comment or "Datei-Dialog: Zielordner"
            elif _is_name_field(step.element):
                step.value = "{filename}"
                step.comment = step.comment or "Datei-Dialog: Dateiname"
        flow.steps.append(step)

    _apply_material_placeholder(flow, material_values)
    _mark_download_step(flow)
    return flow


def _parse_line(line: str) -> Step | None:
    """Eine Skriptzeile in einen Schritt übersetzen.

    Bekannte Aktionen bekommen sprechende Namen; alles andere wird
    generisch als `call`/`set_prop` abgebildet, damit auch ALV-Grid- und
    Baum-Methoden abspielbar sind.
    """
    m = RE_SET_PROP.search(line)
    if m:
        element, prop, value = m.group(1), m.group(2), m.group(3)
        action = PROP_ACTIONS.get(prop.lower())
        if action:
            return Step(action, element, _literal(value))
        return Step("set_prop", element, _literal(value), member=prop,
                    comment=f"aus .vbs: .{prop}")

    m = RE_CALL_ARG.search(line)
    if m:
        element, call, arg = m.group(1), m.group(2), m.group(3)
        action = CALL_ACTIONS.get(call.lower())
        args = _split_args(arg)
        if action:
            return Step(action, element, args[0] if args else None)
        return Step("call", element, method=call, args=args,
                    comment=f"aus .vbs: .{call}")

    m = RE_CALL.search(line)
    if m:
        element, call = m.group(1), m.group(2)
        action = CALL_ACTIONS.get(call.lower())
        if action:
            return Step(action, element)
        return Step("call", element, method=call,
                    comment=f"aus .vbs: .{call}")
    return None


def _split_args(raw: str) -> list:
    """Argumentliste einer VBS-Methode zerlegen: 'a', 5, "b, c" -> [...]"""
    args: list = []
    current = ""
    in_string = False
    for char in raw.strip().strip("()"):
        if char == '"':
            in_string = not in_string
            current += char
        elif char == "," and not in_string:
            args.append(_literal(current))
            current = ""
        else:
            current += char
    if current.strip():
        args.append(_literal(current))
    return args


def _literal(raw: str):
    """VBS-Literal in einen Python-Wert wandeln."""
    value = raw.strip().rstrip(";")
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('""', '"')
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def _is_path_field(element: str) -> bool:
    up = element.upper()
    return any(h in up for h in PATH_FIELD_HINTS)


def _is_name_field(element: str) -> bool:
    up = element.upper()
    return any(h in up for h in NAME_FIELD_HINTS)


def _apply_material_placeholder(
        flow: ScriptFlow, candidates: list[tuple[int, str, str]]) -> None:
    """Setzt {material} in die Felder, die die Materialnummer bekommen.

    Kommt derselbe Zahlenwert mehrfach vor (z. B. Von/Bis-Feld einer
    Select-Option), werden alle Vorkommen ersetzt.
    """
    if not candidates:
        return
    # Häufigsten Wert als Materialnummer annehmen (Von/Bis identisch).
    from collections import Counter

    counts = Counter(value for _i, _e, value in candidates)
    material_value = counts.most_common(1)[0][0]
    first = True
    for index, element, value in candidates:
        if value != material_value:
            continue
        flow.steps[index].value = "{material}"
        flow.steps[index].comment = "Materialnummer"
        if first:
            flow.material_field = element
            first = False
    # Andere Zahlenfelder bleiben unverändert (z. B. Werk, Layoutnummer).


def _mark_download_step(flow: ScriptFlow) -> None:
    """Merkt sich den Schritt, der den Download auslöst.

    Heuristik: der letzte Tastendruck vor dem ersten Datei-Dialog-Feld,
    sonst der letzte press-Schritt überhaupt.
    """
    # 1) Methode, deren Name nach Download klingt (ALV-Toolbar u. a.)
    for i, step in enumerate(flow.steps):
        haystack = " ".join(
            [step.method or "", step.element or ""]
            + [str(a) for a in step.args])
        if step.action in ("call", "press") and DOWNLOAD_HINTS.search(haystack):
            flow.download_step_index = i
            step.comment = step.comment or "löst den Download aus"
            return
    # 2) Sonst: letzter Tastendruck vor dem Datei-Dialog
    dialog_index = next(
        (i for i, s in enumerate(flow.steps)
         if isinstance(s.value, str)
         and s.value in ("{target_dir}", "{filename}", "{target_path}")),
        None)
    if dialog_index is not None:
        for i in range(dialog_index - 1, -1, -1):
            if flow.steps[i].action in ("press", "send_vkey", "call"):
                flow.download_step_index = i
                flow.steps[i].comment = (flow.steps[i].comment
                                         or "löst den Download aus")
                return
    for i in range(len(flow.steps) - 1, -1, -1):
        if flow.steps[i].action == "press":
            flow.download_step_index = i
            return


def describe(flow: ScriptFlow) -> str:
    """Menschenlesbare Übersicht des importierten Ablaufs."""
    lines = [
        f"Ablauf {flow.name!r}"
        + (f", Transaktion {flow.transaction}" if flow.transaction else ""),
        f"Materialnummer-Feld: {flow.material_field or 'NICHT ERKANNT'}",
        f"Schritte: {len(flow.steps)}",
        "",
    ]
    for i, s in enumerate(flow.steps, start=1):
        detail = ""
        if s.action == "call":
            arglist = ", ".join(repr(a) for a in s.args)
            detail = f".{s.method}({arglist})"
        elif s.action == "set_prop":
            detail = f".{s.member} = {s.value!r}"
        elif s.value is not None:
            detail = f" = {s.value!r}"
        marker = " <== DOWNLOAD" if i - 1 == flow.download_step_index else ""
        note = f"   # {s.comment}" if s.comment else ""
        lines.append(
            f"{i:3}. {s.action:<18} {s.element}{detail}{note}{marker}")
    if not flow.material_field:
        lines += [
            "",
            "WARNUNG: Kein Feld mit einer Materialnummer erkannt. Bitte im",
            "erzeugten YAML den passenden Schritt auf value: '{material}'",
            "setzen und material_field eintragen.",
        ]
    return "\n".join(lines)
