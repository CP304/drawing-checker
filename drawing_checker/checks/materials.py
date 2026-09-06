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

import re
from dataclasses import dataclass, field

from .base import CheckContext

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


MATERIALS: list[Material] = [
    # --- Baustähle ---------------------------------------------------------
    Material("S235JR", [r"S\s*235\s*JR?\w*", r"1\.0038", r"1\.0037"],
             "baustahl", weldable="ja", zinc=True),
    Material("S355J2", [r"S\s*355\s*(?:J2|JR|J0|K2)?(?:\+N|\+AR)?", r"1\.0577",
                        r"1\.0570"],
             "baustahl", weldable="ja", zinc=True),
    # --- Vergütungsstähle --------------------------------------------------
    Material("C45", [r"\bC45(?:E|R)?\b", r"1\.0503", r"1\.1191"],
             "verguetung", weldable="bedingt", hardenable={"qt"}, zinc=True,
             note="Schweißen nur mit Vorwärmung/Nachbehandlung"),
    Material("42CrMo4", [r"42\s*CrMo\s*4(?:\s*\+QT)?", r"1\.7225"],
             "verguetung", weldable="bedingt", hardenable={"qt", "nitr"},
             note="Schweißen nur mit Vorwärmung/Nachbehandlung"),
    Material("34CrNiMo6", [r"34\s*CrNiMo\s*6", r"1\.6582"],
             "verguetung", weldable="bedingt", hardenable={"qt", "nitr"}),
    # --- Einsatzstähle -----------------------------------------------------
    Material("16MnCr5", [r"16\s*MnCr\s*5", r"1\.7131"],
             "einsatz", weldable="bedingt", hardenable={"case", "qt"}),
    Material("20MnCr5", [r"20\s*MnCr\s*5", r"1\.7147"],
             "einsatz", weldable="bedingt", hardenable={"case", "qt"}),
    Material("C15", [r"\bC15(?:E|R)?\b", r"1\.0401"],
             "einsatz", weldable="ja", hardenable={"case"}, zinc=True),
    # --- Automatenstähle (Schwefel/Blei -> nicht schweißgeeignet) ----------
    Material("11SMnPb30", [r"11\s*SMnPb\s*30", r"1\.0718"],
             "automaten", weldable="nein", zinc=True,
             note="Automatenstahl (Pb/S): nicht schweißgeeignet"),
    Material("11SMn30", [r"11\s*SMn\s*30", r"9\s*SMn\s*28", r"1\.0715"],
             "automaten", weldable="nein", zinc=True,
             note="Automatenstahl (S): nicht schweißgeeignet"),
    # --- Nichtrostende Stähle ---------------------------------------------
    Material("1.4301 (X5CrNi18-10)", [r"1\.4301", r"X5CrNi18-?10", r"\bV2A\b",
                                      r"AISI\s*304\b"],
             "nirosta", weldable="ja"),
    Material("1.4404 (X2CrNiMo17-12-2)", [r"1\.4404", r"X2CrNiMo17-?12-?2",
                                          r"\bV4A\b", r"AISI\s*316L?\b"],
             "nirosta", weldable="ja"),
    Material("1.4571", [r"1\.4571", r"X6CrNiMoTi17-?12-?2"],
             "nirosta", weldable="ja"),
    Material("1.4305 (X8CrNiS18-9)", [r"1\.4305", r"X8CrNiS18-?9",
                                      r"AISI\s*303\b"],
             "nirosta_auto", weldable="nein",
             note="Automaten-Edelstahl (S-legiert): nicht schweißgeeignet – "
                  "bei Schweißteilen 1.4301/1.4404 verwenden"),
    Material("1.4057", [r"1\.4057", r"X17CrNi16-?2"],
             "nirosta", weldable="bedingt", hardenable={"qt"}),
    # --- Gusswerkstoffe ----------------------------------------------------
    Material("EN-GJL-250", [r"EN[-\s]?GJL[-\s]?\d{3}", r"\bGG[-\s]?2[05]\b"],
             "guss", weldable="nein", castable=True,
             note="Grauguss: Schmelzschweißen nicht zulässig (nur Sonderverfahren)"),
    Material("EN-GJS-400-15", [r"EN[-\s]?GJS[-\s]?\d{3}(?:[-\s]?\d{1,2})?",
                               r"\bGGG[-\s]?[456]0\b"],
             "guss", weldable="bedingt", castable=True,
             note="Sphäroguss: Schweißen nur als qualifiziertes Sonderverfahren"),
    Material("EN AC-AlSi10Mg", [r"EN\s*AC[-\s]?4\d{4}", r"AlSi10Mg", r"AlSi12"],
             "alu", weldable="bedingt", castable=True, anodize=False),
    # --- Aluminium-Knetlegierungen ----------------------------------------
    Material("EN AW-5754 (AlMg3)", [r"EN\s*AW[-\s]?5754", r"AlMg3\b"],
             "alu", weldable="ja", anodize=True),
    Material("EN AW-6060/6063", [r"EN\s*AW[-\s]?606[03]", r"AlMgSi0[,.]5"],
             "alu", weldable="ja", anodize=True),
    Material("EN AW-6082", [r"EN\s*AW[-\s]?6082", r"AlSi1MgMn", r"AlMgSi1\b"],
             "alu", weldable="ja", anodize=True),
    Material("EN AW-7075", [r"EN\s*AW[-\s]?7075", r"AlZn5[,.]5MgCu"],
             "alu", weldable="nein", anodize=True,
             note="7075: schmelzschweißen nicht zulässig (Heißrissneigung)"),
    # --- Kupferwerkstoffe --------------------------------------------------
    Material("CuZn39Pb3", [r"CuZn39Pb3", r"2\.0401", r"\bMs58\b"],
             "kupfer", weldable="nein",
             note="Bleihaltiges Messing: nicht schweißgeeignet"),
    Material("CuZn37", [r"CuZn37\b", r"2\.0321"], "kupfer", weldable="bedingt"),
    # --- Kunststoffe -------------------------------------------------------
    Material("PA6", [r"\bPA\s*6(?:\.6|6)?(?:\s*GF\d{2})?\b"], "kunststoff",
             weldable="nein"),
    Material("POM", [r"\bPOM(?:[-\s]?C|[-\s]?H)?\b"], "kunststoff",
             weldable="nein"),
    Material("PTFE", [r"\bPTFE\b"], "kunststoff", weldable="nein"),
    Material("PE-HD/PE1000", [r"\bPE[-\s]?(?:HD|1000|500)\b"], "kunststoff",
             weldable="nein"),
]

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
                                         "kupfer", "kunststoff"):
            snippet, bbox, page = zinc
            ctx.add("MAT.COATING_CONFLICT",
                    f"Widerspruch: Verzinkung („{snippet}“) auf {primary.name} "
                    f"ist fachlich unsinnig",
                    bbox=bbox, page=page)
        anod = _find_context(ctx, RE_ANODIZE)
        if anod and primary.category != "alu":
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
OBSOLETE_NORMS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"ISO\s*1302\b", re.IGNORECASE),
     "ISO 1302 wurde durch ISO 21920-1 ersetzt"),
    (re.compile(r"DIN\s*6784\b", re.IGNORECASE),
     "DIN 6784 wurde durch ISO 13715 ersetzt"),
    (re.compile(r"DIN\s*7168\b", re.IGNORECASE),
     "DIN 7168 ist zurückgezogen – Allgemeintoleranzen nach ISO 2768/ISO 22081"),
    (re.compile(r"DIN\s*3141\b", re.IGNORECASE),
     "DIN 3141 (Oberflächendreiecke) ist zurückgezogen – ISO 21920 verwenden"),
    (re.compile(r"DIN\s*(?:ISO\s*)?1101\s*:\s*(?:19|200)\d", re.IGNORECASE),
     "Veralteter Ausgabestand der ISO 1101 referenziert"),
    (re.compile(r"DIN\s*8570\b", re.IGNORECASE),
     "DIN 8570 wurde durch ISO 13920 ersetzt (Schweißkonstruktionen)"),
]


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
