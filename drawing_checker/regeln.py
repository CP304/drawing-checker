"""Regelwerk: Kontext, Registrierung, Profile und die Pflege der YAMLs.

Hier steht die Mechanik (was ein Finding ist, welches Profil welche Regel
scharf schaltet) - das Fachwissen selbst liegt in rules/*.yaml.
"""
from __future__ import annotations

# ======================================================================
# base
# ======================================================================
# Check-Basis: Regelprofile (YAML) und gemeinsamer Kontext für alle Checks.



import copy
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .kern import Finding, PackageContent, Severity
from .zeichnung import DrawingPdf

log = logging.getLogger(__name__)

RULES_DIR = Path(__file__).resolve().parent / "rules"


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

# Befunde, die nicht vom erkannten Text abhängen und deshalb auch bei
# OCR-Grundlage ihre volle Härte behalten.
OCR_INDEPENDENT = {"DOC.NO_PDF", "DOC.NO_TEXT", "DOC.OCR", "GEO.UNIT_MISMATCH",
                   "GEO.ASSEMBLY"}

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
            from .zeichnung import find_feature_frames
            try:
                self._frames = find_feature_frames(self.pdf)
            except Exception:  # Stub-PDFs in Tests haben kein doc
                self._frames = []
        return self._frames

    def add(self, code: str, text: str, *, severity: Severity | None = None,
            bbox=None, page: int = 0, detail: str = "") -> None:
        """Finding aufnehmen; bei OCR-Grundlage wird die Härte gedeckelt.

        Beruht der Text auf OCR, ist jede Aussage „Angabe fehlt" nur so
        sicher wie die Erkennung. Solche Befunde werden deshalb auf
        „Prüfen" heruntergestuft – ausgenommen Befunde, die gar nicht vom
        Text abhängen (fehlendes PDF im Paket).
        """
        sev = severity if severity is not None else self.profile.severity(code)
        if (sev >= Severity.ERROR and code not in OCR_INDEPENDENT
                and getattr(self.pdf, "ocr_used", False)):
            sev = Severity.WARNING
            detail = (detail + " " if detail else "") + (
                "Herabgestuft: die Zeichnung wurde per OCR gelesen, ein "
                "Erkennungsfehler ist nicht auszuschließen – am Original "
                "prüfen.")
        self.findings.append(
            Finding(code=code, severity=sev, text=text, bbox=bbox, page=page, detail=detail)
        )


# ======================================================================
# rules_check
# ======================================================================
# Validierung der handgepflegten Wissenspakete (YAML).
#
# Für Anwender, die rules-Dateien manuell nachpflegen:
#
#     drawing-checker --check-rules
#
# prüft alle Regelordner (mitgeliefert + externe `regeln/`-Ordner) und meldet
# Fehler in Klartext mit Datei und Eintrag – bevor ein Prüflauf damit startet.
# Die GUI führt dieselbe Prüfung beim Start aus und zeigt Probleme als Warnung.



import re
from dataclasses import dataclass
from pathlib import Path

import yaml


VALID_CATEGORIES = {
    "baustahl", "verguetung", "einsatz", "automaten", "nirosta",
    "nirosta_auto", "guss", "stahlguss", "alu", "kupfer", "titan",
    "magnesium", "kunststoff", "verbund",
}
VALID_WELDABLE = {"ja", "bedingt", "nein"}
VALID_HARDENABLE = {"qt", "case", "nitr"}


@dataclass
class Issue:
    file: str
    where: str
    problem: str

    def __str__(self) -> str:
        return f"[{self.file}] {self.where}: {self.problem}"


def validate_rules() -> tuple[list[Issue], dict[str, int]]:
    """Prüft alle Wissenspakete; liefert (Probleme, Statistik)."""
    issues: list[Issue] = []
    stats = {"materialien": 0, "normen": 0, "profile": 0, "beschaffung": 0,
             "halbzeuge": 0, "ordner": len(rules_dirs())}

    # ---------------------------------------------------------- materials
    seen_names: set[str] = set()
    for f in rules_files("materials*.yaml"):
        data, err = _load_yaml(f)
        if err:
            issues.append(Issue(f.name, "Datei", err))
            continue
        entries = data.get("materials")
        if entries is None:
            issues.append(Issue(f.name, "Datei",
                                "Schlüssel 'materials:' fehlt auf oberster Ebene"))
            continue
        for i, e in enumerate(entries, start=1):
            where = f"Eintrag {i} ({e.get('name', '?') if isinstance(e, dict) else e!r})"
            if not isinstance(e, dict):
                issues.append(Issue(f.name, where, "Eintrag ist kein Mapping"))
                continue
            for key in ("name", "patterns", "category"):
                if key not in e:
                    issues.append(Issue(f.name, where, f"Pflichtfeld '{key}' fehlt"))
            name = e.get("name")
            if name in seen_names:
                issues.append(Issue(f.name, where,
                                    f"Werkstoffname doppelt: {name!r}"))
            elif name:
                seen_names.add(name)
            if e.get("category") and e["category"] not in VALID_CATEGORIES:
                issues.append(Issue(
                    f.name, where,
                    f"unbekannte category {e['category']!r} "
                    f"(erlaubt: {', '.join(sorted(VALID_CATEGORIES))})"))
            if e.get("weldable") and str(e["weldable"]) not in VALID_WELDABLE:
                issues.append(Issue(f.name, where,
                                    f"weldable muss ja/bedingt/nein sein, "
                                    f"nicht {e['weldable']!r}"))
            for h in e.get("hardenable", []) or []:
                if h not in VALID_HARDENABLE:
                    issues.append(Issue(f.name, where,
                                        f"unbekanntes hardenable-Verfahren {h!r} "
                                        f"(erlaubt: qt, case, nitr)"))
            for pat in e.get("patterns", []) or []:
                perr = _check_regex(pat)
                if perr:
                    issues.append(Issue(f.name, where, perr))
            stats["materialien"] += 1

    # -------------------------------------------------------------- norms
    for f in rules_files("norms*.yaml"):
        data, err = _load_yaml(f)
        if err:
            issues.append(Issue(f.name, "Datei", err))
            continue
        entries = data.get("obsolete")
        if entries is None:
            issues.append(Issue(f.name, "Datei",
                                "Schlüssel 'obsolete:' fehlt auf oberster Ebene"))
            continue
        for i, e in enumerate(entries, start=1):
            where = f"Eintrag {i}"
            if not isinstance(e, dict):
                issues.append(Issue(f.name, where, "Eintrag ist kein Mapping"))
                continue
            if "pattern" not in e or "message" not in e:
                issues.append(Issue(f.name, where,
                                    "Felder 'pattern' und 'message' sind Pflicht"))
                continue
            perr = _check_regex(e["pattern"])
            if perr:
                issues.append(Issue(f.name, where, perr))
            stats["normen"] += 1

    # ------------------------------------------------------- beschaffung
    for f in rules_files("beschaffung*.yaml"):
        data, err = _load_yaml(f)
        if err:
            issues.append(Issue(f.name, "Datei", err))
            continue
        for key in ("vage", "hausnormen"):
            for i, e in enumerate(data.get(key) or [], start=1):
                where = f"{key}, Eintrag {i}"
                if not isinstance(e, dict):
                    issues.append(Issue(f.name, where, "Eintrag ist kein Mapping"))
                    continue
                if "pattern" not in e or "message" not in e:
                    issues.append(Issue(
                        f.name, where,
                        "Felder 'pattern' und 'message' sind Pflicht"))
                    continue
                perr = _check_regex(e["pattern"])
                if perr:
                    issues.append(Issue(f.name, where, perr))
                stats["beschaffung"] += 1
        for key, values in (data.get("halbzeuge") or {}).items():
            if not isinstance(values, list) or not values:
                issues.append(Issue(f.name, f"halbzeuge/{key}",
                                    "Liste von Zahlen erwartet"))
                continue
            for v in values:
                if not isinstance(v, (int, float)) or v <= 0:
                    issues.append(Issue(f.name, f"halbzeuge/{key}",
                                        f"ungültiges Maß {v!r}"))
            stats["halbzeuge"] += len(values)

    # ------------------------------------------------------------ profiles
    try:
        profiles = load_profiles_data()
        stats["profile"] = len(profiles)
        for pname in profiles:
            try:
                pass  # (im selben Modul)

                prof = load_profile(pname)
            except ValueError as exc:  # zyklisches inherit
                issues.append(Issue("profiles*.yaml", f"Profil {pname!r}", str(exc)))
                continue
            for code, rule in prof.rules.items():
                sev = rule.get("severity")
                if sev and str(sev).lower() not in SEVERITY_BY_NAME:
                    issues.append(Issue(
                        "profiles*.yaml", f"Profil {pname!r}, Regel {code}",
                        f"unbekannte severity {sev!r} "
                        f"(erlaubt: {', '.join(SEVERITY_BY_NAME)})"))
    except yaml.YAMLError as exc:
        issues.append(Issue("profiles*.yaml", "Datei", f"YAML-Fehler: {exc}"))

    return issues, stats


def _load_yaml(f: Path) -> tuple[dict, str]:
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return {}, f"nicht lesbar: {exc}"
    if data is None:
        return {}, ""
    if not isinstance(data, dict):
        return {}, "oberste Ebene muss ein Mapping sein"
    return data, ""


def _check_regex(pattern) -> str:
    if not isinstance(pattern, str) or not pattern.strip():
        return f"pattern ist leer oder kein Text: {pattern!r}"
    try:
        re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        return f"ungültiges Regex-Muster {pattern!r}: {exc}"
    return ""


def format_report(issues: list[Issue], stats: dict[str, int]) -> str:
    lines = [
        "Regelordner: " + ", ".join(str(d) for d in rules_dirs()),
        f"Geladen: {stats['materialien']} Werkstoffe, {stats['normen']} "
        f"Normeinträge, {stats['beschaffung']} Beschaffungsregeln, "
        f"{stats['halbzeuge']} Halbzeugmaße, {stats['profile']} Profile",
    ]
    if issues:
        lines.append(f"\n{len(issues)} Problem(e) gefunden:")
        lines += [f"  - {i}" for i in issues]
        lines.append("\nBitte korrigieren – fehlerhafte Einträge werden beim "
                     "Prüflauf ignoriert.")
    else:
        lines.append("Alle Wissenspakete sind in Ordnung.")
    return "\n".join(lines)
