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
    # Eloxier-Eignung von Alu-Legierungen: "" (gut) | "bedingt" | "schlecht".
    # Praxisfall: falsche Legierung fürs Eloxieren gewählt (Si-/Cu-haltig).
    anodize_quality: str = ""
    castable: bool = False
    density: float | None = None   # g/cm³ – für den Masseabgleich
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
                    anodize_quality=str(e.get("anodize_quality", "") or ""),
                    castable=bool(e.get("castable", False)),
                    density=(float(e["density"]) if e.get("density") else None),
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
RE_ANODIZE_DECOR = re.compile(
    r"eloxier|anodi[sz](?:ed|ation|ing)?\s*(?:type\s*ii\b|farb|schwarz|black"
    r"|natur|clear|dekorativ|decorative)?", re.IGNORECASE)
RE_STUD_WELD = re.compile(
    r"schwei[ßs]bolzen|bolzenschwei[ßs]|stud\s*weld(?:ing|s|ed)?"
    r"|weld(?:ing|ed)?\s*studs?|ISO\s*13918|ISO\s*14555", re.IGNORECASE)
# Reihenfolge-Hinweise, die den Konflikt Schweißen/Verzinken auflösen.
RE_ZINC_SEQUENCE = re.compile(
    r"vor\s+dem\s+(?:feuer)?verzinken|nach\s+dem\s+schwei[ßs]en.{0,30}?verzink"
    r"|erst\s+schwei[ßs]en|geschwei[ßs]t\s*,?\s*(?:dann|danach).{0,20}?verzink"
    r"|weld(?:ed)?\s+(?:before|prior\s+to)\s+galvaniz|galvanized?\s+after\s+weld",
    re.IGNORECASE)
RE_BLACKEN = re.compile(r"brüniert?|black\s*oxid[ei]|schwarzoxid", re.IGNORECASE)
# Passungen (40H7, ⌀22 h6, js9 …) und metrische Gewinde – für den
# Schichtdicken-Check bei Verzinken/Eloxieren.
RE_FIT_TOKEN = re.compile(
    r"[⌀Øø]?\s*\d{1,3}\s*(?:H|h|G|g|F|f|K|k|M(?=\d)|m(?=\d)|N|n|P|p|R|r|S|s"
    r"|JS|js)\d{1,2}\b")
RE_METRIC_THREAD = re.compile(r"\bM\s*\d{1,3}(?:\s*[xX×]\s*\d+(?:[.,]\d+)?)?\b")
RE_COAT_EXCLUDE = re.compile(
    r"freihalten|freigehalten|abdecken|abgedeckt|abkleben|maskier"
    r"|nachschneiden|nacharbeiten|nachreiben|nach\s+dem\s+(?:verzinken"
    r"|eloxieren|beschichten)|masked?|plugged|after\s+(?:coating|galvanizing"
    r"|anodizing)|re-?tap", re.IGNORECASE)
RE_FILLER_309 = re.compile(r"\b309L?\b|\b1\.4332\b|ER\s*309", re.IGNORECASE)
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
        blacken = _find_context(ctx, RE_BLACKEN)
        if blacken and primary.category not in (
                "baustahl", "verguetung", "einsatz", "automaten", "stahlguss",
                "guss"):
            snippet, bbox, page = blacken
            ctx.add("MAT.COATING_CONFLICT",
                    f"Widerspruch: Brünieren („{snippet}“) funktioniert nur "
                    f"auf Stahl/Eisenwerkstoffen, Werkstoff ist {primary.name}",
                    bbox=bbox, page=page)

    # --- Eloxier-Eignung der Alu-Legierung (Praxisfall: falsche Legierung) --
    if ctx.profile.enabled("MAT.ANODIZE_ALLOY") and primary.category == "alu":
        anod = _find_context(ctx, RE_ANODIZE)
        if anod and primary.anodize_quality in ("schlecht", "bedingt"):
            snippet, bbox, page = anod
            if primary.anodize_quality == "schlecht":
                ctx.add("MAT.ANODIZE_ALLOY",
                        f"Legierung {primary.name} ist zum Eloxieren ungeeignet "
                        f"(„{snippet}“)",
                        bbox=bbox, page=page, detail=primary.note)
            else:
                ctx.add("MAT.ANODIZE_ALLOY",
                        f"Legierung {primary.name} nur bedingt eloxierbar – "
                        f"Anforderung an die Eloxalschicht klären",
                        severity=ctx.profile.severity("MAT.ANODIZE_LIMITED"),
                        bbox=bbox, page=page, detail=primary.note)

    # --- Schweißbolzen / Reihenfolge Schweißen–Verzinken --------------------
    zinc_ctx = _find_context(ctx, RE_ZINC)
    stud = _find_context(ctx, RE_STUD_WELD)
    if ctx.profile.enabled("PROC.STUD_ON_ZINC") and stud and zinc_ctx:
        snippet, bbox, page = stud
        ctx.add("PROC.STUD_ON_ZINC",
                f"Bolzenschweißen („{snippet}“) auf feuerverzinktem Teil – "
                f"Zinkschicht verhindert prozesssichere Bolzenschweißung",
                bbox=bbox, page=page,
                detail="Bolzen vor dem Verzinken schweißen oder Schweißfläche "
                       "beim Verzinken abdecken – Reihenfolge auf der Zeichnung "
                       "eindeutig vorgeben.")
    elif (ctx.profile.enabled("PROC.WELD_ZINC_ORDER") and zinc_ctx
          and _find_context(ctx, RE_WELD)
          and not _find_context(ctx, RE_ZINC_SEQUENCE)):
        snippet, bbox, page = zinc_ctx
        ctx.add("PROC.WELD_ZINC_ORDER",
                "Schweißen und Verzinken auf derselben Zeichnung, aber keine "
                "Reihenfolge angegeben",
                bbox=bbox, page=page,
                detail="Üblich: erst schweißen, dann feuerverzinken. Ohne "
                       "Angabe drohen Schweißen auf Zinkschicht (Poren, "
                       "Zinkdämpfe) oder unverzinkte Nahtzonen.")

    # --- Schichtdicke vs. Passung/Gewinde (Verzinken/Eloxieren) -------------
    if ctx.profile.enabled("COAT.FIT"):
        coating = zinc_ctx or _find_context(ctx, RE_ANODIZE)
        if coating and not _find_context(ctx, RE_COAT_EXCLUDE):
            fit = _find_context(ctx, RE_FIT_TOKEN)
            thread = _find_context(ctx, RE_METRIC_THREAD)
            target = fit or thread
            if target:
                what = "Passung" if fit else "Gewinde"
                snippet, bbox, page = target
                ctx.add("COAT.FIT",
                        f"Beschichtung ({coating[0]}) und {what} "
                        f"(„{snippet}“) ohne Freihalte-/Nacharbeitsvermerk",
                        bbox=bbox, page=page,
                        detail="Zink-/Eloxalschicht verändert das Maß "
                               "(Feuerverzinkung 50–150 µm). Passflächen/"
                               "Gewinde freihalten, abdecken oder Nacharbeit "
                               "(nachschneiden/reiben) vorgeben.")

    # --- Mischverbindungen beim Schweißen -----------------------------------
    if weld:
        cats = {m.category for m in all_mats}
        steel_cats = cats & {"baustahl", "verguetung", "einsatz", "automaten",
                             "stahlguss"}
        snippet, bbox, page = weld
        if ctx.profile.enabled("WELD.MIXED") and "alu" in cats and steel_cats:
            ctx.add("WELD.MIXED",
                    "Widerspruch: Aluminium und Stahl auf einer "
                    "Schweißzeichnung – schmelzschweißen ist nicht möglich",
                    bbox=bbox, page=page,
                    detail="Mischverbindung Al/Fe nur über Sonderverfahren "
                           "(Reib-/Explosionsschweißen) oder mechanisch fügen.")
        elif (ctx.profile.enabled("WELD.MIXED_FILLER")
              and steel_cats and cats & {"nirosta", "nirosta_auto"}
              and not _find_context(ctx, RE_FILLER_309)):
            ctx.add("WELD.MIXED_FILLER",
                    "Schwarz-Weiß-Verbindung (Edelstahl + un-/niedriglegierter "
                    "Stahl) ohne Zusatzwerkstoff-Angabe",
                    bbox=bbox, page=page,
                    detail="Für Mischverbindungen Zusatzwerkstoff vorgeben "
                           "(üblich 309L / 1.4332), sonst Aufmischungsrisse.")

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
