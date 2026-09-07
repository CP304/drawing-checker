"""Kommandozeilen-Werkzeuge für den SAP-Durchstich.

--sap-import-vbs DATEI   Mitschnitt einlesen, Ablauf anzeigen und speichern
--sap-show-flow          gespeicherten Ablauf anzeigen
--sap-dry-run [MATNR]    Ablauf gegen eine simulierte Session abspielen
                         (prüft Platzhalter und Reihenfolge ohne SAP)
--sap-test MATNR         eine Materialnummer echt über SAP holen
--sap-dump               Elementbaum des aktuellen SAP-Bildes ausgeben
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_FLOW_NAME = "ymatdocs_flow.yaml"


def import_vbs(vbs_path: Path, out_path: Path | None = None) -> int:
    from .sap_ablauf import describe, parse_vbs

    if not vbs_path.is_file():
        print(f"Datei nicht gefunden: {vbs_path}")
        return 2
    from .sap_ablauf import uebernehmen

    target = out_path or _default_flow_path()
    flow, verstanden, zeilen = uebernehmen(vbs_path, target)
    print(describe(flow))
    print()
    print("Kurzfassung:")
    for zeile in zeilen:
        print(f"  {zeile}")
    print(f"\nAblauf gespeichert: {target}")
    print("Nächster Schritt: `drawing-checker --sap-dry-run 4711` "
          "(prüft den Ablauf ohne SAP), danach `--sap-test <echte Nummer>`.")
    if not flow.material_field:
        print("\nACHTUNG: Materialnummer-Feld wurde nicht erkannt. Bitte im "
              "YAML den betreffenden Schritt auf value: '{material}' setzen.")
        return 1
    return 0


def show_flow(flow_path: Path | None = None) -> int:
    from .sap_ablauf import describe
    from .sap_ymatdocs import load_flow

    flow, source = load_flow(flow_path)
    if source is None:
        print("Kein importierter Ablauf gefunden – es greift der Notnagel.")
        print("Mit `--sap-import-vbs <datei.vbs>` einlesen.\n")
    else:
        print(f"Quelle: {source}\n")
    print(describe(flow))
    return 0 if source else 1


def dry_run(material: str = "4711", flow_path: Path | None = None) -> int:
    """Spielt den Ablauf gegen eine simulierte Session ab.

    Prüft ohne SAP: Sind alle Platzhalter gesetzt? Stimmt die Reihenfolge?
    Wird ein Download ausgelöst? Landet die Datei am erwarteten Ort?
    """
    from .sap_ymatdocs import FakeSession
    from .sap_ymatdocs import load_flow, run_ymatdocs

    flow, source = load_flow(flow_path)
    print(f"Trockenlauf mit Ablauf: {source or 'NOTNAGEL (kein Import!)'}")
    with tempfile.TemporaryDirectory() as tmp:
        target_dir = Path(tmp) / "pakete"
        expected = target_dir / f"{material}.zip"
        popup_trigger, download_trigger = _dry_run_triggers(flow)
        session = FakeSession(download_target=expected,
                              popup_after=popup_trigger,
                              download_trigger=download_trigger)
        steps_log: list[str] = []

        def on_step(index, step, resolved):
            if step.action == "call":
                detail = "." + step.method + "(" + ", ".join(
                    repr(a) for a in step.args) + ")"
            elif step.action == "set_prop":
                detail = f".{step.member} = {resolved!r}"
            else:
                detail = "" if resolved is None else f" = {resolved!r}"
            steps_log.append(f"  {index + 1:3}. {step.action:<18} "
                             f"{step.element}{detail}")

        try:
            result = run_ymatdocs(session, material, target_dir,
                                  flow_path=flow_path, watch_dirs=[],
                                  on_step=on_step, timeout_s=10)
        except Exception as exc:
            print("\n".join(steps_log))
            print(f"\nTrockenlauf FEHLGESCHLAGEN: {exc}")
            if source is None:
                print("Ursache: Es ist kein .vbs-Mitschnitt importiert – der "
                      "Notnagel-Ablauf kann nicht funktionieren.\n"
                      "Zuerst `--sap-import-vbs <datei.vbs>` ausführen.")
            return 1
        print("\n".join(steps_log))
        print(f"\nTrockenlauf ok – Paket würde liegen unter: {result.name}")
        print(_dry_run_summary(flow, session, material, popup_trigger,
                               download_trigger))

    unresolved = [s for s in flow.steps
                  if isinstance(s.value, str) and "{" in s.value
                  and s.value not in ("{material}", "{target_dir}",
                                      "{filename}", "{target_path}")]
    if unresolved:
        print("\nWARNUNG: unbekannte Platzhalter in Schritten: "
              + ", ".join(s.value for s in unresolved))
        return 1
    if not flow.material_field:
        print("\nWARNUNG: Kein Materialnummer-Feld im Ablauf markiert.")
        return 1
    if source is None:
        print("\nACHTUNG: Geprüft wurde nur der Notnagel-Ablauf. Erst mit "
              "dem echten Mitschnitt (--sap-import-vbs) ist der Trockenlauf "
              "aussagekräftig.")
        return 1
    return 0


def sap_test(material: str, system: str = "P11",
             flow_path: Path | None = None,
             out_dir: Path | None = None) -> int:
    """Holt eine einzelne Materialnummer über die echte SAP-Verbindung."""
    from .sap_sitzung import describe_session, diagnose_failure
    from .sap_sitzung import SapGuiAdapter

    out = out_dir or Path.cwd() / "sap_test"
    out.mkdir(parents=True, exist_ok=True)
    adapter = SapGuiAdapter(connection_name=system, flow_path=flow_path,
                            diagnose_dir=out)
    try:
        adapter.ensure_ready()
    except Exception as exc:
        print(f"Verbindung fehlgeschlagen: {exc}")
        return 2
    print(describe_session(adapter.session))
    try:
        zip_path = adapter.fetch_package(material, out)
    except Exception as exc:
        print(f"\nAbruf fehlgeschlagen: {exc}")
        try:
            report = diagnose_failure(adapter.session, material, out)
            print(f"Diagnose geschrieben: {report}")
            print("Darin steht der Elementbaum des aktuellen Bildes – daraus "
                  "lassen sich die richtigen Element-IDs ablesen.")
        except Exception:
            pass
        return 1

    size = zip_path.stat().st_size
    print(f"\nPaket geladen: {zip_path} ({size} Bytes)")
    _describe_package(zip_path)
    return 0


def dump_screen(system: str = "P11") -> int:
    from .sap_sitzung import describe_session, dump_screen as dump
    from .sap_sitzung import SapGuiAdapter

    adapter = SapGuiAdapter(connection_name=system)
    try:
        adapter.ensure_ready()
    except Exception as exc:
        print(f"Verbindung fehlgeschlagen: {exc}")
        return 2
    print(describe_session(adapter.session))
    print()
    print(dump(adapter.session))
    for window in ("wnd[1]", "wnd[2]"):
        try:
            if adapter.session.FindById(window, False) is not None:
                print(f"\n--- Dialog {window} ---")
                print(dump(adapter.session, window))
        except Exception:
            pass
    return 0


# ---------------------------------------------------------------- Intern
def _default_flow_path() -> Path:
    from .regeln import rules_dirs

    for directory in rules_dirs():
        if directory.name == "regeln":
            return directory / DEFAULT_FLOW_NAME
    return Path.cwd() / "regeln" / DEFAULT_FLOW_NAME


def _download_trigger(flow) -> str | None:
    """Element/Aktion, die den Download anstößt (Auslöseschritt des Ablaufs)."""
    if flow.download_step_index is None:
        return None
    step = flow.steps[flow.download_step_index]
    if step.action == "send_vkey":
        return f"vkey:{step.value}"
    return step.element


def _dialog_confirm_trigger(flow) -> str | None:
    """Schaltfläche, mit der der Datei-Dialog bestätigt wird.

    In SAP entsteht die Datei erst, wenn im Dialog gespeichert wird – der
    Trockenlauf bildet das nach, damit auch das Füllen von Pfad und
    Dateiname geprüft wird.
    """
    last = None
    for step in flow.steps:
        if step.element.startswith("wnd[1]") and step.action in (
                "press", "call", "send_vkey"):
            last = (f"vkey:{step.value}" if step.action == "send_vkey"
                    else step.element)
    return last


def _dry_run_triggers(flow) -> tuple[str | None, str | None]:
    """(Popup-Auslöser, Download-Auslöser) für die simulierte Session.

    Gibt es im Ablauf einen Datei-Dialog, öffnet der Auslöseschritt das
    Fenster wnd[1] und erst dessen Bestätigung schreibt die Datei. Ohne
    Dialog (stiller Download) schreibt der Auslöseschritt direkt.
    """
    trigger = _download_trigger(flow)
    confirm = _dialog_confirm_trigger(flow)
    if confirm:
        return trigger, confirm
    return trigger, trigger


def _dry_run_summary(flow, session, material: str,
                     popup_trigger: str | None,
                     download_trigger: str | None) -> str:
    """Kurzbericht: Was hat der Ablauf tatsächlich getan?"""
    written = [(e, v) for a, e, v in session.log if a == "set_text"]
    material_fields = [e for e, v in written if str(v) == material]
    lines = ["\nZusammenfassung:",
             f"  Materialnummer geschrieben in: "
             + (", ".join(material_fields) or "NIRGENDS (!)"),
             f"  Download ausgelöst durch: {popup_trigger or 'unbekannt'}"]
    if download_trigger and download_trigger != popup_trigger:
        lines.append(f"  Datei-Dialog bestätigt mit: {download_trigger}")
    else:
        lines.append("  Kein Datei-Dialog im Ablauf – stiller Download in den "
                     "SAP-Standardordner wird überwacht.")
    dialog_fields = [e for e, v in written
                     if e.startswith(("wnd[1]", "wnd[2]"))]
    if dialog_fields:
        lines.append(f"  Dialogfelder gefüllt: {', '.join(dialog_fields)}")
    if not material_fields:
        lines.append("  ACHTUNG: Die Materialnummer landet in keinem Feld – "
                     "im YAML den richtigen Schritt auf '{material}' setzen.")
    return "\n".join(lines)


def _describe_package(zip_path: Path) -> None:
    import zipfile

    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
    except zipfile.BadZipFile:
        print("Inhalt: KEINE gültige ZIP-Datei – bitte prüfen, ob der "
              "Download vollständig war.")
        return
    print(f"Inhalt ({len(names)} Dateien):")
    for name in names[:20]:
        print(f"  {name}")
    pdfs = [n for n in names if n.lower().endswith(".pdf")]
    steps = [n for n in names if n.lower().endswith((".stp", ".step"))]
    print(f"\n-> {len(pdfs)} PDF, {len(steps)} STEP erkannt.")
    if not pdfs:
        print("   ACHTUNG: kein PDF im Paket – Prüfung wäre nicht möglich.")
