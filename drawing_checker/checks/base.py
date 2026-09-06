"""Check-Basis: Regelprofile (YAML) und gemeinsamer Kontext für alle Checks."""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..core.models import Finding, PackageContent, Severity
from ..drawing.pdfdoc import DrawingPdf

log = logging.getLogger(__name__)

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"

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


def load_profile(material_group: str, rules_file: Path | None = None) -> RuleProfile:
    """Lädt ein Profil inkl. `inherit`-Auflösung aus rules/profiles.yaml."""
    path = rules_file or (RULES_DIR / "profiles.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    profiles = data.get("profiles", {})
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

    def add(self, code: str, text: str, *, severity: Severity | None = None,
            bbox=None, page: int = 0, detail: str = "") -> None:
        sev = severity if severity is not None else self.profile.severity(code)
        self.findings.append(
            Finding(code=code, severity=sev, text=text, bbox=bbox, page=page, detail=detail)
        )
