"""Orchestrator: arbeitet die Materialliste vollautomatisch ab.

Läuft in einem Worker-Thread (GUI bleibt bedienbar). Fortschritt und
Ergebnisse gehen über Callbacks nach außen; Pause/Abbruch über Events.
Nach jeder Materialnummer werden Zustand und Excel gespeichert – der Lauf
ist damit jederzeit fortsetzbar.
"""
from __future__ import annotations

import logging
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..checks.base import CheckContext, load_profile
from ..checks.drawing_checks import run_drawing_checks
from ..checks.language_check import check_language
from ..checks.step_compare import check_step
from ..drawing.dimensions import extract_dimensions
from ..drawing.pdfdoc import DrawingPdf
from ..report.annotate import annotate
from ..report.excel_writer import ResultWorkbook, read_materials
from ..sap.adapter import MaterialNotFound, SapAdapter, SapUnavailable
from . import package as pkg
from .housekeeping import (
    DiskFull, DiskGuard, cleanup_package, free_mb, release_memory,
)
from .models import JobStatus, MaterialResult, RunConfig, Severity
from .state import RunState

log = logging.getLogger(__name__)

MAX_JOB_RETRIES = 2   # technische Retries je Materialnummer (nach SAP-Recovery)


@dataclass
class Progress:
    total: int = 0
    done: int = 0
    current: str = ""
    ok: int = 0
    findings: int = 0
    failed: int = 0
    message: str = ""
    eta_s: float | None = None   # geschätzte Restdauer


@dataclass
class Callbacks:
    """GUI-Hooks; alle optional und aus dem Worker-Thread aufgerufen."""

    on_progress: Callable[[Progress], None] = lambda p: None
    on_result: Callable[[MaterialResult], None] = lambda r: None
    on_log: Callable[[str], None] = lambda m: None
    on_finished: Callable[[Progress], None] = lambda p: None


class Orchestrator:
    def __init__(self, config: RunConfig, adapter: SapAdapter,
                 callbacks: Callbacks | None = None, resume: bool = False):
        self.config = config
        self.adapter = adapter
        self.cb = callbacks or Callbacks()
        self.pause_event = threading.Event()   # gesetzt = pausiert
        self.stop_event = threading.Event()
        self.progress = Progress()

        self.run_dir = self._resolve_run_dir(resume)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "pakete").mkdir(exist_ok=True)
        self.state = (RunState.load(config, self.run_dir) if resume
                      else RunState(config, self.run_dir))
        self.profile = load_profile(config.material_group)
        self.report_path: Path | None = None
        self._durations: list[float] = []
        self._thread: threading.Thread | None = None
        self.guard = DiskGuard(self.run_dir / "pakete",
                               min_free_mb=config.min_free_mb)
        self._freed_mb = 0.0

    def _resolve_run_dir(self, resume: bool) -> Path:
        base = self.config.output_dir
        if resume:
            runs = sorted((p for p in base.glob("lauf_*") if p.is_dir()),
                          reverse=True)
            if runs:
                return runs[0]
        return base / time.strftime("lauf_%Y%m%d_%H%M%S")

    # ------------------------------------------------------------- Steuerung
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="pruef-worker",
                                        daemon=True)
        self._thread.start()

    def pause(self) -> None:
        self.pause_event.set()

    def resume(self) -> None:
        self.pause_event.clear()

    def stop(self) -> None:
        self.stop_event.set()
        self.pause_event.clear()

    def join(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    # ------------------------------------------------------------ Hauptlauf
    def _run(self) -> None:
        # Lauf-Logdatei im Ergebnisordner (zusätzlich zum globalen Log).
        run_log = logging.FileHandler(self.run_dir / "lauf.log",
                                      encoding="utf-8")
        run_log.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S"))
        logging.getLogger().addHandler(run_log)
        try:
            self._run_inner()
        except Exception as exc:  # letzte Verteidigungslinie des Threads
            log.exception("Prüflauf abgebrochen")
            self.progress.message = f"Lauf abgebrochen: {exc}"
            self.cb.on_log(self.progress.message)
        finally:
            logging.getLogger().removeHandler(run_log)
            run_log.close()
            self.cb.on_finished(self.progress)

    def _run_inner(self) -> None:
        materials = read_materials(self.config)
        workbook = ResultWorkbook(self.config)
        self.progress.total = len(materials)
        self._log(f"{len(materials)} Materialnummern in Spalte "
                  f"{self.config.material_column} gefunden")

        # Bereits erledigte (Resume) vorab in die Zählung übernehmen.
        todo: list[tuple[int, str]] = []
        for row, material in materials:
            if self.state.is_done(row, material):
                result = self.state.results[f"{row}:{material}"]
                self._count(result)
                self.progress.done += 1
                self.cb.on_result(result)
            else:
                todo.append((row, material))
        if self.progress.done:
            self._log(f"Fortsetzen: {self.progress.done} bereits geprüft, "
                      f"{len(todo)} offen")

        self._log(f"Freier Speicherplatz: {free_mb(self.run_dir):.0f} MB")
        for row, material in todo:
            if self.stop_event.is_set():
                self._log("Lauf vom Anwender abgebrochen")
                break
            self._wait_if_paused()
            if self.stop_event.is_set():
                break
            try:
                hinweis = self.guard.check()
            except DiskFull as exc:
                self.progress.message = str(exc)
                self._log(str(exc))
                break
            if hinweis:
                self._log(hinweis)

            self.progress.current = material
            self.cb.on_progress(self.progress)
            result = self._process_with_retries(row, material)

            self.state.record(result)
            workbook.write_result(result)
            workbook.save()
            self._count(result)
            self.progress.done += 1
            self._durations.append(max(result.duration_s, 0.1))
            remaining = self.progress.total - self.progress.done
            if self._durations and remaining > 0:
                avg = sum(self._durations) / len(self._durations)
                self.progress.eta_s = avg * remaining
            else:
                self.progress.eta_s = None
            self.cb.on_result(result)
            self.cb.on_progress(self.progress)

        # Abschluss: Zusammenfassung in Excel + HTML-Bericht
        all_results = list(self.state.results.values())
        try:
            workbook.finalize(all_results)
            workbook.save()
        except Exception:
            log.exception("Excel-Zusammenfassung fehlgeschlagen")
        try:
            self._write_findings_csv(all_results)
        except Exception:
            log.exception("findings.csv fehlgeschlagen")
        try:
            from ..report.html_report import write_html_report

            self.report_path = write_html_report(
                self.config, all_results, self.run_dir, self.profile.name,
                duration_s=time.time() - self.state.started)
            self._log(f"Bericht erstellt: {self.report_path.name}")
        except Exception:
            log.exception("HTML-Bericht fehlgeschlagen")

        self.progress.current = ""
        self.progress.message = (
            f"Fertig: {self.progress.ok} ok, {self.progress.findings} mit "
            f"Findings, {self.progress.failed} fehlgeschlagen "
            f"(von {self.progress.total})")
        if self._freed_mb:
            self._log(f"Aufgeräumt: {self._freed_mb:.0f} MB Pakete gelöscht, "
                      f"{free_mb(self.run_dir):.0f} MB frei")
        self._log(self.progress.message)

    def _process_with_retries(self, row: int, material: str) -> MaterialResult:
        last_error = ""
        for attempt in range(1, MAX_JOB_RETRIES + 2):
            try:
                return self._process_one(row, material)
            except SapUnavailable as exc:
                last_error = str(exc)
                self._log(f"{material}: SAP nicht verfügbar ({exc}) – "
                          f"Recovery, Versuch {attempt}")
                try:
                    self.adapter.ensure_ready()
                except SapUnavailable as exc2:
                    last_error = str(exc2)
            except MaterialNotFound as exc:
                result = MaterialResult(material=material, row=row,
                                        status=JobStatus.FINDINGS)
                result.findings.append(_finding_no_package(str(exc)))
                return result
            except Exception as exc:
                log.error("Unerwarteter Fehler bei %s:\n%s", material,
                          traceback.format_exc())
                last_error = f"{type(exc).__name__}: {exc}"
                break
        return MaterialResult(material=material, row=row,
                              status=JobStatus.FAILED, error=last_error)

    # ------------------------------------------------- Eine Materialnummer
    def _process_one(self, row: int, material: str) -> MaterialResult:
        """Eine Materialnummer holen, prüfen und danach aufräumen.

        Das Paket wird nach der Prüfung gelöscht (sofern nicht
        `keep_packages`): Bild, Findings und Bericht liegen dann schon im
        Ergebnisordner, das ZIP wird nicht mehr gebraucht. Ohne das wächst
        ein Lauf über eine ganze Materialgruppe um Gigabyte.
        """
        zip_dir = self.run_dir / "pakete"
        zip_path = self.adapter.fetch_package(material, zip_dir)
        content = None
        try:
            try:
                content = pkg.extract_package(zip_path, zip_dir, material)
            except pkg.PackageError as exc:
                raise MaterialNotFound(str(exc)) from exc
            return self._check_package(row, material, content)
        finally:
            freed = cleanup_package(
                content.work_dir if content else None, zip_path,
                keep=self.config.keep_packages)
            self._freed_mb += freed
            # Nach jeder Materialnummer aufräumen: Renderpuffer und
            # OpenCascade-Objekte belegen sonst dauerhaft Speicher.
            release_memory()

    def _check_package(self, row: int, material: str,
                       content: pkg.PackageContent) -> MaterialResult:
        t0 = time.time()
        result = MaterialResult(material=material, row=row,
                                status=JobStatus.RUNNING)

        if content.drawing_pdf is None:
            result.status = JobStatus.FINDINGS
            result.findings.append(_finding_no_package(
                "Kein PDF im YMATDOCS-Paket – Zeichnung fehlt"))
            result.duration_s = time.time() - t0
            return result

        with DrawingPdf(content.drawing_pdf) as pdf:
            ctx = CheckContext(material=material, pdf=pdf, package=content,
                               profile=self.profile)
            if len(content.pdfs) > 1 and self.profile.enabled("DOC.MULTI_PDF"):
                ctx.add("DOC.MULTI_PDF",
                        f"{len(content.pdfs)} PDFs im Paket – geprüft wurde "
                        f"„{content.drawing_pdf.name}“")
            has_text = bool(pdf.words())
            if not has_text:
                ctx.add("DOC.NO_TEXT",
                        "Kein auswertbarer Text (kein Textlayer, OCR nicht "
                        "verfügbar) – textbasierte Checks entfallen, bitte "
                        "manuell prüfen")
            elif pdf.ocr_used:
                result.ocr_used = True
                ctx.add("DOC.OCR",
                        "Zeichnung ohne Textlayer – Prüfung basiert auf OCR "
                        "(eingeschränkte Zuverlässigkeit)",
                        detail=pdf.ocr_note() + ". Unsichere Zahlen werden "
                               "nicht als Maß übernommen; fehlende Angaben "
                               "können auch an der Erkennung liegen – bei "
                               "Beanstandungen die Zeichnung ansehen.")

            # Prüfdokumentation: Änderungsdatum + Fertigungsverfahren
            from ..checks.processes import detect_processes
            from ..drawing.metadata import extract_revision_date

            result.drawing_rev_date = extract_revision_date(pdf)
            result.processes = detect_processes(pdf)

            dims = []
            scale_note = ""
            mass_note = ""
            if has_text:
                run_drawing_checks(ctx)
                check_language(ctx)
                dims = extract_dimensions(
                    pdf, float(self.profile.params.get("max_plausible_dim", 6000)))
                # Tiefenprüfungen auf Basis der extrahierten Maße
                from ..checks.dimension_checks import run_dimension_checks
                from ..checks.doc_checks import run_doc_checks
                from ..checks.gps_checks import run_gps_checks
                from ..checks.mass_checks import check_mass_plausibility
                from ..checks.process_checks import run_process_checks
                from ..checks.purchasing_checks import run_purchasing_checks

                run_gps_checks(ctx, dims)
                run_dimension_checks(ctx, dims)
                run_process_checks(ctx, dims)
                run_purchasing_checks(ctx, dims)
                run_doc_checks(ctx)
                mass_note = check_mass_plausibility(ctx, dims)
                from ..checks.scale_checks import check_scale_consistency

                scale_note = check_scale_consistency(ctx, dims)
            result.step_summary = check_step(ctx, dims)
            if has_text:
                result.step_summary = " | ".join(
                    x for x in (result.step_summary, scale_note, mass_note)
                    if x)

            result.findings = ctx.findings
            shot = self.run_dir / f"{pkg._safe_name(material)}.png"
            try:
                result.screenshot = annotate(pdf, result, shot)
            except Exception:
                log.exception("Annotation fehlgeschlagen für %s", material)

        worst = result.worst_severity
        result.status = (JobStatus.OK if worst is None or worst <= Severity.INFO
                         else JobStatus.FINDINGS)
        result.duration_s = time.time() - t0
        return result

    def _write_findings_csv(self, results: list[MaterialResult]) -> None:
        """Maschinenlesbarer Export je Lauf – Grundlage für KPI-Auswertungen
        über mehrere Läufe (häufigste Mängel, Lieferanten-/Gruppenvergleich)."""
        import csv

        from .models import SEVERITY_LABEL

        path = self.run_dir / "findings.csv"
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["Materialnummer", "Excel-Zeile", "Regel", "Bewertung",
                        "Text", "Detail", "Geprüft am", "Status"])
            for r in results:
                for f in r.sorted_findings():
                    w.writerow([r.material, r.row, f.code,
                                SEVERITY_LABEL[f.severity], f.text, f.detail,
                                r.checked_at, r.status.value])

    # ---------------------------------------------------------------- Utils
    def _wait_if_paused(self) -> None:
        if self.pause_event.is_set():
            self._log("Pausiert …")
            while self.pause_event.is_set() and not self.stop_event.is_set():
                time.sleep(0.2)
            if not self.stop_event.is_set():
                self._log("Fortgesetzt")

    def _count(self, result: MaterialResult) -> None:
        if result.status == JobStatus.OK:
            self.progress.ok += 1
        elif result.status == JobStatus.FINDINGS:
            self.progress.findings += 1
        elif result.status == JobStatus.FAILED:
            self.progress.failed += 1

    def _log(self, msg: str) -> None:
        log.info(msg)
        self.cb.on_log(msg)


def _finding_no_package(text: str):
    from .models import BBox, Finding  # noqa: F401 (BBox für Symmetrie)

    return Finding(code="DOC.NO_PDF", severity=Severity.BLOCKER, text=text)
