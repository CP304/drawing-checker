"""Check-Basis: Regelprofile (YAML) und gemeinsamer Kontext für alle Checks."""
from __future__ import annotations

import copy
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..core.models import Finding, PackageContent, Severity
from ..drawing.pdfdoc import DrawingPdf

log = logging.getLogger(__name__)

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"


def rules_dirs() -> list[Path]:
    """Alle Regelordner in Ladereihenfolge (spätere überschreiben frühere).

    1. Mitgelieferte Pakete im Programm (RULES_DIR).
    2. Ordner aus der Umgebungsvariablen DRAWING_CHECKER_RULES.
    3. Ordner `regeln/` neben der ausführbaren Datei (PyInstaller-.exe)
       bzw. im Arbeitsverzeichnis – dort pflegen Anwender ihre YAMLs
       manuell nach, ohne das Programm anzufassen.
    """
    import sys

    dirs = [RULES_DIR]
    env = os.environ.get("DRAWING_CHECKER_RULES")
    if env:
        dirs.append(Path(env))
    if getattr(sys, "frozen", False):
        dirs.append(Path(sys.executable).resolve().parent / "regeln")
    dirs.append(Path.cwd() / "regeln")
    seen: set[Path] = set()
    out = []
    for d in dirs:
        if d.is_dir() and d not in seen:
            seen.add(d)
            out.append(d)
    return out


def rules_files(pattern: str) -> list[Path]:
    """Alle Wissenspaket-Dateien zu einem Muster über alle Regelordner."""
    files: list[Path] = []
    for d in rules_dirs():
        files.extend(sorted(d.glob(pattern)))
    return files

SEVERITY_BY_NAME = {
    "info": Severity.INFO,
    "warning": Severity.WARNING,
    "error": Severity.ERROR,
    "blocker": Severity.BLOCKER,
}


@dataclass
class RuleProfile:
    """Aufgelöstes Regelprofil einer Materialgruppe."""

    name: str
    rules: dict[str, dict] = field(default_factory=dict)
    step_tolerance: dict = field(default_factory=lambda: {"rel": 0.05, "abs": 2.0})
    params: dict = field(default_factory=dict)

    def enabled(self, code: str) -> bool:
        return bool(self.rules.get(code, {}).get("enabled", False))

    def severity(self, code: str, default: Severity = Severity.ERROR) -> Severity:
        name = self.rules.get(code, {}).get("severity")
        return SEVERITY_BY_NAME.get(str(name).lower(), default) if name else default

    def rule_param(self, code: str, key: str, default=None):
        return self.rules.get(code, {}).get(key, default)


def load_profiles_data(rules_file: Path | None = None) -> dict:
    """Sammelt alle profiles*.yaml über alle Regelordner (deep-merged).

    Externe Ordner (regeln/ neben der .exe, DRAWING_CHECKER_RULES) können
    damit einzelne Regeln/Severities überschreiben oder eigene Profile
    ergänzen, ohne die mitgelieferte Datei anzufassen.
    """
    if rules_file is not None:
        data = yaml.safe_load(rules_file.read_text(encoding="utf-8")) or {}
        return data.get("profiles", {})
    merged: dict = {}
    for f in rules_files("profiles*.yaml"):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            log.error("Profildatei %s nicht lesbar: %s", f, exc)
            continue
        merged = _deep_merge(merged, data.get("profiles", {}))
    return merged


def load_profile(material_group: str, rules_file: Path | None = None) -> RuleProfile:
    """Lädt ein Profil inkl. `inherit`-Auflösung aus den profiles*.yaml."""
    profiles = load_profiles_data(rules_file)
    if material_group not in profiles:
        log.warning("Profil %r unbekannt, nutze 'default'", material_group)
        material_group = "default"

    merged: dict = {}
    chain: list[str] = []
    name: str | None = material_group
    while name:
        if name in chain:
            raise ValueError(f"Zyklische inherit-Kette in Profilen: {chain + [name]}")
        chain.append(name)
        name = profiles.get(name, {}).get("inherit")
    for pname in reversed(chain):
        merged = _deep_merge(merged, profiles.get(pname, {}))
    merged.pop("inherit", None)

    return RuleProfile(
        name=material_group,
        rules=merged.get("rules", {}),
        step_tolerance=merged.get("step_tolerance", {"rel": 0.05, "abs": 2.0}),
        params=merged.get("params", {}),
    )


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


@dataclass
class CheckContext:
    """Alles, was ein Check über den aktuellen Prüfling wissen darf."""

    material: str
    pdf: DrawingPdf
    package: PackageContent
    profile: RuleProfile
    findings: list[Finding] = field(default_factory=list)
    _frames: list | None = field(default=None, repr=False)

    @property
    def feature_frames(self) -> list:
        """Grafisch erkannte Toleranzrahmen (einmalig ermittelt)."""
        if self._frames is None:
            from ..drawing.fcf import find_feature_frames
            try:
                self._frames = find_feature_frames(self.pdf)
            except Exception:  # Stub-PDFs in Tests haben kein doc
                self._frames = []
        return self._frames

    def add(self, code: str, text: str, *, severity: Severity | None = None,
            bbox=None, page: int = 0, detail: str = "") -> None:
        sev = severity if severity is not None else self.profile.severity(code)
        self.findings.append(
            Finding(code=code, severity=sev, text=text, bbox=bbox, page=page, detail=detail)
        )
