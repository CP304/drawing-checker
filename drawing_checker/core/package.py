"""Entpacken und Klassifizieren der YMATDOCS-ZIP-Pakete.

YMATDOCS liefert je Materialnummer ein ZIP mit mindestens einem PDF
(der Zeichnung), manchmal STEP-Dateien und manchmal nativen CAD-Daten,
die ignoriert werden.
"""
from __future__ import annotations

import logging
import re
import shutil
import zipfile
from pathlib import Path

from .models import PackageContent

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
