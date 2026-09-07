"""Kernbausteine: Datenmodelle, Paketzugriff, Laufzustand, Haushalt.

Vier kleine Bausteine, die alles andere benutzt - deshalb liegen sie in
einem Modul: was ein Finding ist, wie ein YMATDOCS-Paket ausgepackt wird,
wo ein unterbrochener Lauf weitermacht, und wie man Speicher und Platte
wieder freibekommt.
"""
from __future__ import annotations

# ======================================================================
# models
# ======================================================================
# Zentrale Datenmodelle des Drawing Checkers.



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
    # Dauerlauf-Haushalt: entpackte Pakete nach der Prüfung löschen und
    # anhalten, bevor die Platte voll ist.
    keep_packages: bool = False     # True = Pakete zur Fehlersuche behalten
    min_free_mb: int = 500          # Sicherheitsreserve auf dem Laufwerk
    # Blockweise Abarbeitung: nach je `batch_size` Materialnummern wird ein
    # Zwischenstand gesichert (Excel, Zustand, Bericht), der Speicher
    # freigegeben und die SAP-Session aufgeräumt. 0 = alles am Stück.
    batch_size: int = 25
    batch_pause_s: float = 0.0      # optionale Atempause zwischen Blöcken
    max_sap_sessions: int = 5       # Obergrenze offener SAP-Fenster


# ======================================================================
# package
# ======================================================================
# Entpacken und Klassifizieren der YMATDOCS-ZIP-Pakete.
#
# YMATDOCS liefert je Materialnummer ein ZIP mit mindestens einem PDF
# (der Zeichnung), manchmal STEP-Dateien und manchmal nativen CAD-Daten,
# die ignoriert werden.



import logging
import re
import shutil
import zipfile
from pathlib import Path


log = logging.getLogger(__name__)

PDF_EXT = {".pdf"}
STEP_EXT = {".stp", ".step", ".p21"}
# Native CAD- und Begleitformate, die bewusst ignoriert werden.
IGNORED_EXT = {
    ".catpart", ".catproduct", ".catdrawing", ".cgr",
    ".prt", ".asm", ".drw", ".sldprt", ".sldasm", ".slddrw",
    ".dwg", ".dxf", ".jt", ".tif", ".tiff", ".xml", ".txt", ".log",
}


class PackageError(Exception):
    """ZIP fehlt, ist leer oder nicht lesbar."""


def extract_package(zip_path: Path, work_dir: Path, material: str) -> PackageContent:
    """Entpackt das ZIP nach work_dir/<material>/ und klassifiziert den Inhalt."""
    if not zip_path.exists() or zip_path.stat().st_size == 0:
        raise PackageError(f"ZIP-Paket fehlt oder ist leer: {zip_path}")

    target = work_dir / _safe_name(material)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    try:
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                # Zip-Slip-Schutz: nur flache, bereinigte Dateinamen zulassen.
                name = Path(info.filename).name
                if not name or name.startswith("."):
                    continue
                dest = target / name
                with zf.open(info) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
    except zipfile.BadZipFile as exc:
        raise PackageError(f"ZIP-Paket nicht lesbar: {zip_path} ({exc})") from exc

    content = classify_files(list(target.iterdir()), material)
    content.zip_path = zip_path
    content.work_dir = target
    log.info(
        "Paket %s: %d PDF, %d STEP, %d ignoriert",
        material, len(content.pdfs), len(content.steps), len(content.ignored),
    )
    return content


def classify_files(files: list[Path], material: str) -> PackageContent:
    content = PackageContent()
    for f in sorted(files):
        ext = f.suffix.lower()
        if ext in PDF_EXT:
            content.pdfs.append(f)
        elif ext in STEP_EXT:
            content.steps.append(f)
        else:
            content.ignored.append(f)

    # Bei mehreren PDFs: das wahrscheinlichste Zeichnungs-PDF nach vorn sortieren.
    if len(content.pdfs) > 1:
        content.pdfs.sort(key=lambda p: _drawing_score(p, material), reverse=True)
    return content


def _drawing_score(pdf: Path, material: str) -> tuple[int, int]:
    """Heuristik: Materialnummer im Dateinamen schlägt alles, dann Dateigröße."""
    stem = pdf.stem.lower()
    digits = re.sub(r"\D", "", material)
    hit = 1 if (material.lower() in stem or (digits and digits in stem)) else 0
    return (hit, pdf.stat().st_size)


def _safe_name(material: str) -> str:
    return re.sub(r"[^\w.-]", "_", material.strip()) or "unbenannt"


# ======================================================================
# state
# ======================================================================
# Persistenter Lauf-Zustand: macht jeden Lauf nach Absturz fortsetzbar.
#
# Nach jeder abgeschlossenen Materialnummer wird der Zustand atomar auf Platte
# geschrieben. "Fortsetzen" in der GUI lädt den Zustand und überspringt alles,
# was bereits einen Endstatus hat.



import json
import logging
import os
import tempfile
import time
from dataclasses import asdict
from pathlib import Path



STATE_NAME = "lauf_zustand.json"


def finde_fortsetzbaren_lauf(config: RunConfig) -> tuple[Path, int, int] | None:
    """Sucht einen unfertigen Lauf, der zu DIESER Excel-Auswahl gehört.

    Früher wurde beim Fortsetzen einfach der neueste Lauf-Ordner genommen –
    das konnte den Lauf einer ganz anderen Materialgruppe fortsetzen.
    Verglichen werden deshalb Datei, Blatt und Spalte.

    Rückgabe: (Ordner, bereits geprüft, insgesamt bekannt) oder None.
    """
    basis = config.output_dir
    if not basis.is_dir():
        return None
    for ordner in sorted((p for p in basis.glob("lauf_*") if p.is_dir()),
                         reverse=True):
        try:
            data = json.loads((ordner / STATE_NAME).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        cfg = data.get("config", {})
        if (Path(cfg.get("excel_path", "")) != config.excel_path
                or cfg.get("sheet_name") != config.sheet_name
                or cfg.get("material_column") != config.material_column):
            continue
        fertig = sum(1 for r in data.get("results", [])
                     if r.get("status") in ("ok", "findings", "skipped"))
        if fertig:
            return (ordner, fertig, len(data.get("results", [])))
    return None


class RunState:
    def __init__(self, config: RunConfig, run_dir: Path):
        self.config = config
        self.run_dir = run_dir
        self.results: dict[str, MaterialResult] = {}  # key: f"{row}:{material}"
        self.started = time.time()

    # ---------------------------------------------------------------- Zugriff
    @staticmethod
    def key(result: MaterialResult) -> str:
        return f"{result.row}:{result.material}"

    def is_done(self, row: int, material: str) -> bool:
        r = self.results.get(f"{row}:{material}")
        return r is not None and r.status in (
            JobStatus.OK, JobStatus.FINDINGS, JobStatus.SKIPPED
        )

    def record(self, result: MaterialResult) -> None:
        self.results[self.key(result)] = result
        self.save()

    # ------------------------------------------------------------ Persistenz
    @property
    def path(self) -> Path:
        return self.run_dir / STATE_NAME

    def save(self) -> None:
        data = {
            "version": 1,
            "started": self.started,
            "config": {
                "excel_path": str(self.config.excel_path),
                "sheet_name": self.config.sheet_name,
                "material_column": self.config.material_column,
                "header_row": self.config.header_row,
                "material_group": self.config.material_group,
                "sap_connection": self.config.sap_connection,
            },
            "results": [self._result_to_json(r) for r in self.results.values()],
        }
        # Atomar schreiben, damit ein Absturz mitten im Schreiben den
        # Zustand nicht zerstört.
        fd, tmp = tempfile.mkstemp(dir=self.run_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    @staticmethod
    def _result_to_json(r: MaterialResult) -> dict:
        d = asdict(r)
        d["status"] = r.status.value
        d["screenshot"] = str(r.screenshot) if r.screenshot else None
        for f, fd_ in zip(r.findings, d["findings"]):
            fd_["severity"] = int(f.severity)
        return d

    @classmethod
    def load(cls, config: RunConfig, run_dir: Path) -> "RunState":
        """Lädt einen früheren Zustand; fehlende/kaputte Datei => leerer Zustand."""
        state = cls(config, run_dir)
        try:
            data = json.loads((run_dir / STATE_NAME).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return state
        pass  # (im selben Modul)

        state.started = data.get("started", state.started)
        for rd in data.get("results", []):
            findings = [
                Finding(
                    code=f["code"],
                    severity=Severity(f["severity"]),
                    text=f["text"],
                    bbox=BBox(**f["bbox"]) if f.get("bbox") else None,
                    page=f.get("page", 0),
                    detail=f.get("detail", ""),
                )
                for f in rd.get("findings", [])
            ]
            result = MaterialResult(
                material=rd["material"],
                row=rd["row"],
                status=JobStatus(rd["status"]),
                findings=findings,
                screenshot=Path(rd["screenshot"]) if rd.get("screenshot") else None,
                error=rd.get("error", ""),
                step_summary=rd.get("step_summary", ""),
                duration_s=rd.get("duration_s", 0.0),
                ocr_used=rd.get("ocr_used", False),
                checked_at=rd.get("checked_at", ""),
                drawing_rev_date=rd.get("drawing_rev_date", ""),
                processes=list(rd.get("processes", [])),
            )
            state.results[cls.key(result)] = result
        log.info("Lauf-Zustand geladen: %d Ergebnisse", len(state.results))
        return state


# ======================================================================
# housekeeping
# ======================================================================
# Platten- und Aufräumverwaltung für lange Prüfläufe.
#
# Ein Lauf über eine ganze Materialgruppe holt hunderte ZIP-Pakete und
# entpackt sie. Ohne Aufräumen wächst der Ergebnisordner um mehrere
# Gigabyte, und der Lauf stirbt mitten in der Nacht an einer vollen Platte –
# mit einem Traceback, den niemand deuten kann.
#
# Deshalb:
#   * Nach jeder Materialnummer wird das entpackte Paket (und auf Wunsch das
#     ZIP) gelöscht. Gebraucht wird davon nichts mehr: annotiertes Bild,
#     Findings und Bericht liegen im Ergebnisordner.
#   * Vor jeder Materialnummer wird der freie Platz geprüft. Wird es eng,
#     räumt der Lauf zuerst selbst auf; hilft das nicht, hält er GEORDNET an,
#     statt unkontrolliert abzustürzen – das Ergebnis bis dahin bleibt
#     verwertbar und der Lauf ist fortsetzbar.



import logging
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MIN_FREE_MB = 500


class DiskFull(Exception):
    """Zu wenig Platz, um den Lauf sinnvoll fortzusetzen."""


def free_mb(path: Path) -> float:
    """Freier Platz auf dem Laufwerk von `path` in MB (-1 = unbekannt)."""
    try:
        return shutil.disk_usage(path).free / (1024 * 1024)
    except OSError:
        return -1.0


def dir_size_mb(path: Path) -> float:
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
    except OSError:
        pass
    return total / (1024 * 1024)


def cleanup_package(work_dir: Path | None, zip_path: Path | None,
                    keep: bool = False) -> float:
    """Entpackten Ordner und ZIP einer Materialnummer entfernen.

    Liefert die freigegebene Größe in MB. Mit `keep=True` bleibt alles
    liegen (Fehlersuche an einzelnen Paketen).
    """
    if keep:
        return 0.0
    freed = 0.0
    for target in (work_dir, zip_path):
        if target is None or not target.exists():
            continue
        try:
            if target.is_dir():
                freed += dir_size_mb(target)
                shutil.rmtree(target, ignore_errors=True)
            else:
                freed += target.stat().st_size / (1024 * 1024)
                target.unlink()
        except OSError as exc:
            log.warning("Aufräumen von %s fehlgeschlagen: %s", target, exc)
    return freed


def sweep_packages(package_dir: Path, keep_newest: int = 0) -> float:
    """Notaufräumen: alle (bis auf die neuesten) Pakete löschen."""
    if not package_dir.is_dir():
        return 0.0
    entries = sorted(package_dir.iterdir(),
                     key=lambda p: p.stat().st_mtime if p.exists() else 0,
                     reverse=True)
    freed = 0.0
    for entry in entries[keep_newest:]:
        freed += cleanup_package(entry if entry.is_dir() else None,
                                 None if entry.is_dir() else entry)
    return freed


@dataclass
class DiskGuard:
    """Wacht über den freien Platz während des Laufs."""

    package_dir: Path
    min_free_mb: float = DEFAULT_MIN_FREE_MB

    def check(self) -> str:
        """Vor jeder Materialnummer aufrufen.

        Liefert einen Hinweistext (leer = alles gut) oder wirft DiskFull,
        wenn auch nach dem Aufräumen zu wenig Platz bleibt.
        """
        free = free_mb(self.package_dir)
        if free < 0 or free >= self.min_free_mb:
            return ""
        freed = sweep_packages(self.package_dir)
        free = free_mb(self.package_dir)
        if free >= self.min_free_mb:
            return (f"Wenig Speicherplatz – {freed:.0f} MB Pakete "
                    f"aufgeräumt, jetzt {free:.0f} MB frei")
        raise DiskFull(
            f"Nur noch {free:.0f} MB frei (nötig sind {self.min_free_mb:.0f} "
            f"MB). Der Lauf hält an; bereits geprüfte Zeilen sind gesichert. "
            f"Platz schaffen und mit „Fortsetzen“ weiterlaufen lassen.")


def release_memory() -> None:
    """Speicher einsammeln und ans Betriebssystem zurückgeben.

    Beim Rendern und bei der OCR entstehen Puffer von über 100 MB je Seite.
    Python gibt sie frei, die C-Speicherverwaltung von Linux (glibc) behält
    sie aber im Prozess – über hunderte Materialnummern wächst der Prozess
    dadurch um Gigabyte (gemessen mit `python -m tools.langlauf`).
    `malloc_trim` gibt sie wirklich zurück. Unter Windows regelt das die
    Heap-Verwaltung selbst; dort ist der Aufruf ein wirkungsloser No-op.
    """
    import gc

    gc.collect()
    # PyMuPDF hält einen internen Zwischenspeicher (Schriften, Bilder,
    # gerenderte Objekte) über Dokumentgrenzen hinweg. Über hunderte
    # Zeichnungen sind das Gigabyte – messbar mit tools/langlauf.py.
    try:
        import pymupdf

        pymupdf.TOOLS.store_shrink(100)
    except Exception:      # pragma: no cover - andere PyMuPDF-Fassung
        log.debug("PyMuPDF-Zwischenspeicher nicht leerbar", exc_info=True)
    if not sys.platform.startswith("linux"):
        return
    try:
        import ctypes

        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:      # pragma: no cover - z. B. musl statt glibc
        log.debug("malloc_trim nicht verfügbar", exc_info=True)
