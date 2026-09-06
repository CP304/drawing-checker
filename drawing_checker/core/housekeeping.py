"""Platten- und Aufräumverwaltung für lange Prüfläufe.

Ein Lauf über eine ganze Materialgruppe holt hunderte ZIP-Pakete und
entpackt sie. Ohne Aufräumen wächst der Ergebnisordner um mehrere
Gigabyte, und der Lauf stirbt mitten in der Nacht an einer vollen Platte –
mit einem Traceback, den niemand deuten kann.

Deshalb:
  * Nach jeder Materialnummer wird das entpackte Paket (und auf Wunsch das
    ZIP) gelöscht. Gebraucht wird davon nichts mehr: annotiertes Bild,
    Findings und Bericht liegen im Ergebnisordner.
  * Vor jeder Materialnummer wird der freie Platz geprüft. Wird es eng,
    räumt der Lauf zuerst selbst auf; hilft das nicht, hält er GEORDNET an,
    statt unkontrolliert abzustürzen – das Ergebnis bis dahin bleibt
    verwertbar und der Lauf ist fortsetzbar.
"""
from __future__ import annotations

import logging
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

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
