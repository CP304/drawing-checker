"""Zentrale Datenmodelle des Drawing Checkers."""
from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from pathlib import Path


class Severity(enum.IntEnum):
    """Schwere eines Findings. Reihenfolge = Sortierung (schwerstes zuerst)."""

    INFO = 0      # Hinweis, keine Beanstandung (z. B. "kein STEP vorhanden")
    WARNING = 1   # "nicht nachweisbar" / Plausibilität, manuell nachsehen
    ERROR = 2     # Klare Beanstandung (fehlende Pflichtangabe, deutsche Beschriftung)
    BLOCKER = 3   # K.O.: Geometrie passt nicht / falsche Zeichnung im Paket


SEVERITY_LABEL = {
    Severity.INFO: "Hinweis",
    Severity.WARNING: "Prüfen",
    Severity.ERROR: "Fehler",
    Severity.BLOCKER: "K.O.",
}


@dataclass
class BBox:
    """Achsparalleles Rechteck in PDF-Punkten (Ursprung oben links, PyMuPDF)."""

    x0: float
    y0: float
    x1: float
    y1: float

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)


@dataclass
class Finding:
    """Ein Prüfergebnis eines Checks.

    code: stabiler Regelcode (z. B. "TB.MATERIAL"), erscheint in Excel und Legende.
    bbox: Position auf der Zeichnung (PDF-Koordinaten); None = nur Legendeneintrag.
    page: 0-basierte PDF-Seite, auf die sich bbox bezieht.
    """

    code: str
    severity: Severity
    text: str
    bbox: BBox | None = None
    page: int = 0
    detail: str = ""


class JobStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    OK = "ok"                  # geprüft, keine Findings >= WARNING
    FINDINGS = "findings"      # geprüft, Findings vorhanden
    FAILED = "failed"          # Prüfung technisch fehlgeschlagen (nach Retries)
    SKIPPED = "skipped"        # ungültige Materialnummer o. ä.


@dataclass
class PackageContent:
    """Klassifizierter Inhalt eines YMATDOCS-ZIP-Pakets."""

    zip_path: Path | None = None
    work_dir: Path | None = None
    pdfs: list[Path] = field(default_factory=list)
    steps: list[Path] = field(default_factory=list)
    ignored: list[Path] = field(default_factory=list)

    @property
    def drawing_pdf(self) -> Path | None:
        """Das als Zeichnung ausgewählte PDF (Heuristik in core.package)."""
        return self.pdfs[0] if self.pdfs else None

    @property
    def step_file(self) -> Path | None:
        return self.steps[0] if self.steps else None


@dataclass
class MaterialResult:
    """Gesamtergebnis für eine Materialnummer (eine Excel-Zeile)."""

    material: str
    row: int                                   # 1-basierte Excel-Zeile
    status: JobStatus = JobStatus.PENDING
    findings: list[Finding] = field(default_factory=list)
    screenshot: Path | None = None             # annotiertes Zeichnungsbild
    error: str = ""                            # technischer Fehler bei FAILED
    step_summary: str = ""                     # Vergleichswerte STEP vs. Zeichnung
    duration_s: float = 0.0
    ocr_used: bool = False
    started_at: float = field(default_factory=time.time)
    # --- Prüfdokumentation (Pflichtspalten der Ergebnis-Excel) -------------
    checked_at: str = field(
        default_factory=lambda: time.strftime("%d.%m.%Y %H:%M"))
    drawing_rev_date: str = ""          # spätestes Datum auf der Zeichnung
    processes: list[str] = field(default_factory=list)  # Fertigungsverfahren

    @property
    def worst_severity(self) -> Severity | None:
        return max((f.severity for f in self.findings), default=None)

    def sorted_findings(self) -> list[Finding]:
        return sorted(self.findings, key=lambda f: (-int(f.severity), f.code))


@dataclass
class RunConfig:
    """Konfiguration eines Prüflaufs (aus GUI + config.yaml zusammengesetzt)."""

    excel_path: Path
    sheet_name: str
    material_column: str            # Spaltenbuchstabe, z. B. "C"
    header_row: int                 # 1-basierte Zeile der Überschriften
    output_dir: Path
    material_group: str = "default" # wählt Regel-/Toleranzprofil
    sap_connection: str = "P11"
    mock_source: Path | None = None # gesetzt => MockSapAdapter statt echtem SAP
    sap_flow: Path | None = None    # importierter .vbs-Ablauf (sonst Suchpfade)
