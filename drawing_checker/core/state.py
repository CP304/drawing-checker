"""Persistenter Lauf-Zustand: macht jeden Lauf nach Absturz fortsetzbar.

Nach jeder abgeschlossenen Materialnummer wird der Zustand atomar auf Platte
geschrieben. "Fortsetzen" in der GUI lädt den Zustand und überspringt alles,
was bereits einen Endstatus hat.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from .models import JobStatus, MaterialResult, RunConfig

log = logging.getLogger(__name__)

STATE_NAME = "lauf_zustand.json"


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
        from .models import BBox, Finding, Severity  # lokaler Import: Zyklusfrei

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
            )
            state.results[cls.key(result)] = result
        log.info("Lauf-Zustand geladen: %d Ergebnisse", len(state.results))
        return state
