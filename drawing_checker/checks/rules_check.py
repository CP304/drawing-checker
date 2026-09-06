"""Validierung der handgepflegten Wissenspakete (YAML).

Für Anwender, die rules-Dateien manuell nachpflegen:

    drawing-checker --check-rules

prüft alle Regelordner (mitgeliefert + externe `regeln/`-Ordner) und meldet
Fehler in Klartext mit Datei und Eintrag – bevor ein Prüflauf damit startet.
Die GUI führt dieselbe Prüfung beim Start aus und zeigt Probleme als Warnung.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .base import SEVERITY_BY_NAME, load_profiles_data, rules_dirs, rules_files

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
    stats = {"materialien": 0, "normen": 0, "profile": 0, "ordner": len(rules_dirs())}

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

    # ------------------------------------------------------------ profiles
    try:
        profiles = load_profiles_data()
        stats["profile"] = len(profiles)
        for pname in profiles:
            try:
                from .base import load_profile

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
        f"Normeinträge, {stats['profile']} Profile",
    ]
    if issues:
        lines.append(f"\n{len(issues)} Problem(e) gefunden:")
        lines += [f"  - {i}" for i in issues]
        lines.append("\nBitte korrigieren – fehlerhafte Einträge werden beim "
                     "Prüflauf ignoriert.")
    else:
        lines.append("Alle Wissenspakete sind in Ordnung.")
    return "\n".join(lines)
