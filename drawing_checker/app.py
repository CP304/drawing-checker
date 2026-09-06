"""Einstiegspunkt der Anwendung.

  drawing-checker                     GUI, echtes SAP (Windows)
  drawing-checker --mock ORDNER       GUI, Mock-Adapter (ZIPs aus ORDNER)
  drawing-checker --headless ...      Lauf ohne GUI (für Tests/Automatisierung)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core.models import RunConfig
from .logging_setup import setup_logging
from .sap.adapter import SapAdapter


def build_adapter(config: RunConfig) -> SapAdapter:
    if config.mock_source is not None:
        from .sap.mock import MockSapAdapter

        return MockSapAdapter(config.mock_source)
    from .sap.session import SapGuiAdapter

    return SapGuiAdapter(connection_name=config.sap_connection)


def main() -> int:
    parser = argparse.ArgumentParser(description="Drawing Checker")
    parser.add_argument("--mock", type=Path, metavar="ORDNER",
                        help="Mockmodus: YMATDOCS-ZIPs aus diesem Ordner")
    parser.add_argument("--headless", action="store_true",
                        help="ohne GUI laufen (benötigt --excel/--column)")
    parser.add_argument("--excel", type=Path)
    parser.add_argument("--sheet", default=None)
    parser.add_argument("--column", default=None, help="z. B. C")
    parser.add_argument("--header-row", type=int, default=1)
    parser.add_argument("--profile", default="default")
    parser.add_argument("--system", default="P11")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--check-rules", action="store_true",
                        help="Wissenspakete (YAML) validieren und beenden")
    args = parser.parse_args()

    if args.check_rules:
        from .checks.rules_check import format_report, validate_rules

        issues, stats = validate_rules()
        print(format_report(issues, stats))
        return 1 if issues else 0

    if args.headless:
        return run_headless(args)
    return run_gui(args)


def run_gui(args) -> int:
    from PySide6.QtWidgets import QApplication

    from .gui.main_window import MainWindow, list_profiles

    setup_logging(Path.home() / ".drawing-checker" / "logs")
    app = QApplication(sys.argv)
    app.setApplicationName("Drawing Checker")
    win = MainWindow(build_adapter, list_profiles(), mock_default=args.mock)
    win.show()

    # Handgepflegte Wissenspakete beim Start prüfen: Probleme als Warnung
    # anzeigen (fehlerhafte Einträge werden im Lauf ignoriert, nicht fatal).
    from .checks.rules_check import validate_rules

    issues, _stats = validate_rules()
    if issues:
        from PySide6.QtWidgets import QMessageBox

        text = "\n".join(f"• {i}" for i in issues[:15])
        if len(issues) > 15:
            text += f"\n… und {len(issues) - 15} weitere"
        QMessageBox.warning(
            win, "Regeldateien prüfen",
            "In den Wissenspaketen (YAML) wurden Probleme gefunden. Die "
            "betroffenen Einträge werden ignoriert:\n\n" + text)
    return app.exec()


def run_headless(args) -> int:
    import openpyxl

    from .core.orchestrator import Callbacks, Orchestrator

    if not args.excel or not args.column:
        print("--headless benötigt --excel und --column", file=sys.stderr)
        return 2
    sheet = args.sheet
    if sheet is None:
        wb = openpyxl.load_workbook(args.excel, read_only=True)
        sheet = wb.sheetnames[0]
        wb.close()
    config = RunConfig(
        excel_path=args.excel, sheet_name=sheet,
        material_column=args.column.upper(), header_row=args.header_row,
        output_dir=args.excel.parent / "Ergebnisse",
        material_group=args.profile, sap_connection=args.system,
        mock_source=args.mock,
    )
    setup_logging(config.output_dir / "logs")
    adapter = build_adapter(config)
    adapter.ensure_ready()
    orch = Orchestrator(config, adapter,
                        Callbacks(on_log=lambda m: print(m)),
                        resume=args.resume)
    orch.start()
    orch.join()
    return 0 if orch.progress.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
