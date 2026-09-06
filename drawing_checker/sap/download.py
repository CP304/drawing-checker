"""Erkennung der heruntergeladenen ZIP-Datei.

Wohin YMATDOCS das Paket ablegt, ist bis zum Durchstich unbekannt. Deshalb
werden mehrere Wege gleichzeitig überwacht:

  1. der erwartete Zielpfad (aus dem Datei-Dialog),
  2. der Zielordner insgesamt (falls SAP den Dateinamen selbst vergibt),
  3. zusätzliche Ordner (Windows-Download, SAP-Arbeitsverzeichnis, Temp).

Erkannt wird jede Datei, die nach dem Start des Downloads neu entstanden
ist; gewartet wird, bis ihre Größe stabil ist (Schreibvorgang beendet).
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 180.0
STABLE_SECONDS = 1.5
POLL_INTERVAL_S = 0.4
# Endungen, die als Ergebnis in Frage kommen (SAP legt teils .zip.tmp an).
CANDIDATE_SUFFIXES = (".zip", ".sar", ".rar", ".7z")
TEMP_SUFFIXES = (".tmp", ".part", ".crdownload", ".filepart")


def default_watch_dirs() -> list[Path]:
    """Ordner, in denen ein Download landen könnte."""
    dirs: list[Path] = []
    home = Path.home()
    for candidate in (home / "Downloads", home / "Documents" / "SAP",
                      home / "SAP" / "SAP GUI", Path(os.environ.get("TEMP", ""))
                      if os.environ.get("TEMP") else None):
        if candidate and candidate.is_dir():
            dirs.append(candidate)
    return dirs


@dataclass
class DownloadWatcher:
    """Überwacht mehrere Ordner auf eine neu entstandene Archivdatei."""

    expected: Path | None = None
    watch_dirs: list[Path] = field(default_factory=list)
    timeout_s: float = DEFAULT_TIMEOUT_S
    _before: dict[Path, set[Path]] = field(default_factory=dict, init=False)
    _started: float = field(default=0.0, init=False)

    def start(self) -> None:
        """Ausgangszustand festhalten (vor dem Auslösen des Downloads)."""
        self._started = time.time()
        self._before = {}
        if self.expected is not None:
            # Eine alte Datei gleichen Namens darf nicht als Treffer gelten.
            try:
                self.expected.unlink(missing_ok=True)
            except OSError:
                log.warning("Alte Datei %s ließ sich nicht entfernen",
                            self.expected)
        for directory in self._all_dirs():
            self._before[directory] = set(_list_files(directory))

    def wait(self, abbruch=None) -> Path:
        """Wartet auf die fertige Datei und liefert ihren Pfad.

        Wirft TimeoutError, wenn nichts erscheint. `abbruch` ist eine
        Funktion ohne Argumente; liefert sie True, wird das Warten sofort
        beendet – sonst müsste der Anwender nach dem Abbrechen-Knopf noch
        bis zu drei Minuten auf den Zeitablauf warten.
        """
        deadline = time.time() + self.timeout_s
        stable_since: dict[Path, tuple[int, float]] = {}
        while time.time() < deadline:
            if abbruch is not None and abbruch():
                raise TimeoutError("Download vom Anwender abgebrochen")
            for candidate in self._new_files():
                size = _size(candidate)
                if size <= 0:
                    continue
                last = stable_since.get(candidate)
                if last is not None and last[0] == size:
                    if time.time() - last[1] >= STABLE_SECONDS:
                        log.info("Download erkannt: %s (%d Bytes)",
                                 candidate, size)
                        return candidate
                else:
                    stable_since[candidate] = (size, time.time())
            time.sleep(POLL_INTERVAL_S)
        raise TimeoutError(
            f"Kein Download erkannt (Zielpfad {self.expected}, überwacht: "
            f"{', '.join(str(d) for d in self._all_dirs()) or 'keine Ordner'})")

    # ------------------------------------------------------------- Intern
    def _all_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        if self.expected is not None:
            dirs.append(self.expected.parent)
        for d in self.watch_dirs:
            if d not in dirs:
                dirs.append(d)
        return [d for d in dirs if d.is_dir()]

    def _new_files(self) -> list[Path]:
        found: list[Path] = []
        if self.expected is not None and self.expected.exists():
            found.append(self.expected)
        for directory in self._all_dirs():
            before = self._before.get(directory, set())
            for path in _list_files(directory):
                if path in before or path in found:
                    continue
                if not _is_candidate(path):
                    continue
                if path.stat().st_mtime < self._started - 5:
                    continue      # älter als der Downloadstart
                found.append(path)
        return found


def _list_files(directory: Path) -> list[Path]:
    try:
        return [p for p in directory.iterdir() if p.is_file()]
    except OSError:
        return []


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return -1


def _is_candidate(path: Path) -> bool:
    name = path.name.lower()
    if name.endswith(TEMP_SUFFIXES):
        return False
    return name.endswith(CANDIDATE_SUFFIXES)
