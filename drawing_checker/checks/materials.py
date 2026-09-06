"""Werkstofferkennung und fachliche Widerspruchsprüfung.

Zwei Aufgaben:
  1. Ist überhaupt ein Werkstoff angegeben (erkennbare Bezeichnung, nicht nur
     das Schriftfeld-Label)?
  2. Passen Freitexte/Symbolik/Normbezüge fachlich zum Werkstoff?
     Beispiele: 1.4305 (Automatenstahl, nicht schweißgeeignet) + Schweißnaht;
     nichtrostender Stahl + "feuerverzinkt"; Baustahl S235 + "vergütet";
     Aluminium + ISO 5817 (gilt für Stahl, für Alu: ISO 10042).

Die Werkstoffdatenbank ist bewusst kompakt und konservativ: nur eindeutige
Fälle führen zu einem Fehler, Unsicheres wird als "Prüfen" (warning) gemeldet.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .base import RULES_DIR, CheckContext, rules_files

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Werkstoffdatenbank
# --------------------------------------------------------------------------
# weldable: "ja" | "bedingt" | "nein"
# hardenable: Verfahren, die fachlich sinnvoll sind
#   qt = vergüten/härten, case = einsatzhärten, nitr = nitrieren
# zinc: Feuer-/galvanisch verzinken sinnvoll, anodize: eloxieren sinnvoll


@dataclass
class Material:
    name: str                       # Anzeigename
    patterns: list[str]             # Regex-Alternativen (Nummer + Kurzname)
    category: str                   # baustahl|verguetung|einsatz|automaten|
                                    # nirosta|nirosta_auto|guss|alu|kupfer|kunststoff
    weldable: str = "ja"
    hardenable: set[str] = field(default_factory=set)
    zinc: bool = False
    anodize: bool = False
    castable: bool = False
    note: str = ""


def _load_materials() -> list[Material]:
    """Lädt alle materials*.yaml aus dem rules-Ordner (Wissenspakete)."""
    out: list[Material] = []
    for f in rules_files("materials*.yaml"):
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for e in data.get("materials", []):
            try:
                patterns = [str(p) for p in e["patterns"]]
                for pat in patterns:
                    re.compile(pat)  # Tippfehler sofort erkennen
                out.append(Material(
                    name=e["name"], patterns=patterns,
                    category=e["category"], weldable=e.get("weldable", "ja"),
                    hardenable=set(e.get("hardenable", [])),
                    zinc=bool(e.get("zinc", False)),
                    anodize=bool(e.get("anodize", False)),
                    castable=bool(e.get("castable", False)),
                    note=e.get("note", ""),
                ))
            except (KeyError, TypeError, re.error) as exc:
                # Fehlerhafte Einträge überspringen statt Lauf abbrechen –
                # `drawing-checker --check-rules` zeigt sie dem Pfleger an.
                log.error("Werkstoffeintrag in %s fehlerhaft (%s): %r",
                          f.name, exc, e)
    return out


MATERIALS: list[Material] = _load_materials()

METAL_HT = {"baustahl", "verguetung", "einsatz", "automaten", "nirosta",
            "nirosta_auto"}


@dataclass
class MaterialHit:
    material: Material
    matched: str
    bbox: object
    page: int


def find_materials(ctx: CheckContext) -> list[MaterialHit]:
    """Erkennt alle Werkstoffbezeichnungen mit Fundstelle."""
    hits: list[MaterialHit] = []
    seen: set[str] = set()
    for block in ctx.pdf.blocks():
        for mat in MATERIALS:
            for pat in mat.patterns:
                m = re.search(pat, block.text, re.IGNORECASE)
                if m and mat.name not in seen:
                    seen.add(mat.name)
                    hits.append(MaterialHit(mat, m.group(0), block.bbox,
                                            block.page))
                    break
    return hits


# --------------------------------------------------------------------------
# Kontextsignale in Freitext / Symbolik
# --------------------------------------------------------------------------
RE_WELD = re.compile(
    r"schwei[ßs]|weld|\bwps\b|naht|fillet\s+weld|\bseam\b|ISO\s*2553"
    r"|ISO\s*5817|ISO\s*10042|EN\s*1090|\ba\s?[2-9]\s*[▲△]", re.IGNORECASE)
RE_HT_QT = re.compile(
    r"vergüte|härten|gehärtet|induktivgehärtet|randschichtgehärtet|\+QT\b"
    r"|quench|hardened|tempered|\bHRC\s*\d{2}", re.IGNORECASE)
RE_HT_CASE = re.compile(
    r"einsatzgehärtet|einsatzhärten|aufgekohlt|carburi[sz]ed|case[-\s]harden"
    r"|\bEht\b|\bCHD\b", re.IGNORECASE)
RE_HT_NITR = re.compile(r"nitrier|nitrid(?:ed|ing)|plasmanitrier|\bNHD\b",
                        re.IGNORECASE)
RE_ZINC = re.compile(
    r"feuerverzink|verzink|zinc[-\s]?(?:plated|coated)|galvani[sz]ed"
    r"|hot[-\s]?dip|zn\s*\d+\b|ISO\s*1461|ISO\s*2081", re.IGNORECASE)
RE_ANODIZE = re.compile(r"eloxier|anodi[sz]|anodisiert", re.IGNORECASE)
RE_ISO5817 = re.compile(r"ISO\s*5817", re.IGNORECASE)
RE_ISO10042 = re.compile(r"ISO\s*10042", re.IGNORECASE)
RE_CAST = re.compile(r"\bguss|gussteil|casting|\bcast\b|rohteil|formschräge"
                     r"|draft\s+angle|ISO\s*8062|DCTG|GCTG", re.IGNORECASE)


def _find_context(ctx: CheckContext, regex: re.Pattern):
    for block in ctx.pdf.blocks():
        m = regex.search(block.text)
        if m:
            return m.group(0), block.bbox, block.page
    return None


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------
def check_material_present(ctx: CheckContext, hits: list[MaterialHit]) -> None:
    """MAT.MISSING: Werkstoff muss irgendwo als Bezeichnung erkennbar sein."""
    if not ctx.profile.enabled("MAT.MISSING"):
        return
    if hits:
        return
    label_kws = ctx.profile.rule_param("TB.MATERIAL", "keywords",
                                       ["Werkstoff", "Material"])
    text = ctx.pdf.full_text().lower()
    has_label = any(k.lower() in text for k in label_kws)
    if has_label:
        ctx.add("MAT.MISSING",
                "Werkstoffbezeichnung nicht erkannt (Schriftfeld-Label vorhanden, "
                "aber keine bekannte Bezeichnung gefunden)",
                severity=ctx.profile.severity("MAT.UNKNOWN"),
                detail="Entweder exotischer Werkstoff (Datenbank erweitern) "
                       "oder Angabe fehlt/ist unvollständig.")
    else:
        ctx.add("MAT.MISSING",
                "Kein Werkstoff auf der Zeichnung angegeben",
                detail="Weder Werkstoff-Feld noch erkennbare "
                       "Werkstoffbezeichnung gefunden.")


def check_material_conflicts(ctx: CheckContext, hits: list[MaterialHit]) -> None:
    """Fachliche Widersprüche zwischen Werkstoff und Freitext/Symbolik."""
    if not hits:
        return
    primary = hits[0].material
    all_mats = [h.material for h in hits]

    # --- Schweißen ---------------------------------------------------------
    weld = _find_context(ctx, RE_WELD)
    if weld and ctx.profile.enabled("MAT.WELD_CONFLICT"):
        snippet, bbox, page = weld
        if primary.weldable == "nein":
            ctx.add("MAT.WELD_CONFLICT",
                    f"Widerspruch: Werkstoff {primary.name} ist nicht "
                    f"schweißgeeignet, Zeichnung enthält aber Schweißangaben "
                    f"(„{snippet}“)",
                    bbox=bbox, page=page, detail=primary.note)
        elif primary.weldable == "bedingt":
            ctx.add("MAT.WELD_CONFLICT",
                    f"Werkstoff {primary.name} nur bedingt schweißgeeignet – "
                    f"Schweißangaben prüfen (Vorwärmung/Verfahren spezifiziert?)",
                    severity=ctx.profile.severity("MAT.WELD_LIMITED"),
                    bbox=bbox, page=page, detail=primary.note)

    # --- Wärmebehandlung ---------------------------------------------------
    if ctx.profile.enabled("MAT.HT_CONFLICT"):
        for regex, verfahren, needed in (
            (RE_HT_QT, "Härten/Vergüten", "qt"),
            (RE_HT_CASE, "Einsatzhärten", "case"),
            (RE_HT_NITR, "Nitrieren", "nitr"),
        ):
            hit = _find_context(ctx, regex)
            if not hit:
                continue
            snippet, bbox, page = hit
            if primary.category not in METAL_HT:
                ctx.add("MAT.HT_CONFLICT",
                        f"Widerspruch: {verfahren} („{snippet}“) ist für "
                        f"{primary.name} nicht anwendbar",
                        bbox=bbox, page=page)
            elif needed not in primary.hardenable:
                ctx.add("MAT.HT_CONFLICT",
                        f"Widerspruch: {verfahren} („{snippet}“) passt nicht zu "
                        f"{primary.name} (Werkstoff dafür nicht vorgesehen)",
                        bbox=bbox, page=page,
                        detail="Kohlenstoffgehalt/Legierung prüfen – ggf. "
                               "falscher Werkstoff oder falsche Angabe.")

    # --- Beschichtung ------------------------------------------------------
    if ctx.profile.enabled("MAT.COATING_CONFLICT"):
        zinc = _find_context(ctx, RE_ZINC)
        if zinc and primary.category in ("nirosta", "nirosta_auto", "alu",
                                         "kupfer", "kunststoff", "verbund"):
            snippet, bbox, page = zinc
            ctx.add("MAT.COATING_CONFLICT",
                    f"Widerspruch: Verzinkung („{snippet}“) auf {primary.name} "
                    f"ist fachlich unsinnig",
                    bbox=bbox, page=page)
        anod = _find_context(ctx, RE_ANODIZE)
        if anod and primary.category not in ("alu", "titan"):
            snippet, bbox, page = anod
            ctx.add("MAT.COATING_CONFLICT",
                    f"Widerspruch: Eloxieren („{snippet}“) ist nur für "
                    f"Aluminium möglich, Werkstoff ist {primary.name}",
                    bbox=bbox, page=page)

    # --- Guss --------------------------------------------------------------
    if ctx.profile.enabled("MAT.CAST_CONFLICT"):
        cast = _find_context(ctx, RE_CAST)
        if cast and not any(m.castable for m in all_mats):
            snippet, bbox, page = cast
            ctx.add("MAT.CAST_CONFLICT",
                    f"Gusskontext („{snippet}“), aber {primary.name} ist kein "
                    f"Gusswerkstoff – Werkstoff- oder Textangabe prüfen",
                    bbox=bbox, page=page)

    # --- Normbezug passt zum Werkstoff ------------------------------------
    if ctx.profile.enabled("NORM.MATERIAL_MISMATCH"):
        if primary.category == "alu":
            hit = _find_context(ctx, RE_ISO5817)
            if hit:
                snippet, bbox, page = hit
                ctx.add("NORM.MATERIAL_MISMATCH",
                        "ISO 5817 gilt für Stahl – für Aluminium ist "
                        "ISO 10042 anzugeben",
                        bbox=bbox, page=page)
        elif primary.category not in ("alu",):
            hit = _find_context(ctx, RE_ISO10042)
            if hit and primary.category != "alu":
                snippet, bbox, page = hit
                ctx.add("NORM.MATERIAL_MISMATCH",
                        f"ISO 10042 gilt für Aluminium – Werkstoff ist aber "
                        f"{primary.name} (Stahl: ISO 5817)",
                        bbox=bbox, page=page)


# --------------------------------------------------------------------------
# Normen-Katalog: zurückgezogene/ersetzte Normen
# --------------------------------------------------------------------------
def _load_obsolete_norms() -> list[tuple[re.Pattern, str]]:
    """Lädt alle norms*.yaml aus dem rules-Ordner (Wissenspakete)."""
    out: list[tuple[re.Pattern, str]] = []
    for f in rules_files("norms*.yaml"):
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for e in data.get("obsolete", []):
            try:
                out.append((re.compile(e["pattern"], re.IGNORECASE),
                            e["message"]))
            except (KeyError, re.error) as exc:
                log.error("Normeintrag in %s fehlerhaft (%s): %r",
                          f.name, exc, e)
    return out


OBSOLETE_NORMS: list[tuple[re.Pattern, str]] = _load_obsolete_norms()


def check_obsolete_norms(ctx: CheckContext) -> None:
    if not ctx.profile.enabled("NORM.OBSOLETE"):
        return
    for block in ctx.pdf.blocks():
        for regex, message in OBSOLETE_NORMS:
            if regex.search(block.text):
                ctx.add("NORM.OBSOLETE",
                        f"Veralteter Normbezug: {message}",
                        bbox=block.bbox, page=block.page)


def run_material_checks(ctx: CheckContext) -> None:
    hits = find_materials(ctx)
    check_material_present(ctx, hits)
    check_material_conflicts(ctx, hits)
    check_obsolete_norms(ctx)
