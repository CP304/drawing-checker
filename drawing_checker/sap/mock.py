"""Mock-SAP-Adapter: liefert YMATDOCS-Pakete aus einem Ordner.

Erwartet je Materialnummer eine Datei `<material>.zip` im Quellordner.
Dient der Entwicklung ohne SAP und den End-to-End-Tests; optional lässt
sich ein SAP-Absturz injizieren, um Watchdog/Retry-Pfade zu testen.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from .adapter import MaterialNotFound, SapAdapter, SapUnavailable


class MockSapAdapter(SapAdapter):
    def __init__(self, source_dir: Path, latency_s: float = 0.0,
                 crash_on: set[str] | None = None):
        self.source_dir = Path(source_dir)
        self.latency_s = latency_s
        self.crash_on = crash_on or set()   # Materialien, die 1x "abstürzen"
        self._crashed: set[str] = set()
        self.ready = False

    def ensure_ready(self) -> None:
        if not self.source_dir.is_dir():
            raise SapUnavailable(f"Mock-Quellordner fehlt: {self.source_dir}")
        self.ready = True

    def fetch_package(self, material: str, target_dir: Path) -> Path:
        if not self.ready:
            raise SapUnavailable("Mock-Adapter nicht verbunden (ensure_ready fehlt)")
        if material in self.crash_on and material not in self._crashed:
            # Simulierter Absturz: genau einmal, danach klappt der Retry.
            self._crashed.add(material)
            self.ready = False
            raise SapUnavailable(f"Simulierter SAP-Absturz bei {material}")
        if self.latency_s:
            time.sleep(self.latency_s)
        src = self.source_dir / f"{material}.zip"
        if not src.exists():
            raise MaterialNotFound(
                f"{material}: kein Dokumentpaket vorhanden (Mock)")
        target_dir.mkdir(parents=True, exist_ok=True)
        dst = target_dir / src.name
        shutil.copy2(src, dst)
        return dst

    def close(self) -> None:
        self.ready = False
