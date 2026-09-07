"""Pruefungen zu Werkstoff, Fertigungsverfahren, Masse und Beschaffung.

Was aus dem Werkstoff folgt (Verfahren, Oberflaechenbehandlung, Dichte
und damit das Gewicht) und was der internationale Einkauf braucht
(eindeutige Normen statt Hausnormen, Halbzeugmasse).
"""
from __future__ import annotations

# ======================================================================
# materials
# ======================================================================
# Werkstofferkennung und fachliche Widerspruchsprüfung.
#
# Zwei Aufgaben:
#   1. Ist überhaupt ein Werkstoff angegeben (erkennbare Bezeichnung, nicht nur
#      das Schriftfeld-Label)?
#   2. Passen Freitexte/Symbolik/Normbezüge fachlich zum Werkstoff?
#      Beispiele: 1.4305 (Automatenstahl, nicht schweißgeeignet) + Schweißnaht;
#      nichtrostender Stahl + "feuerverzinkt"; Baustahl S235 + "vergütet";
#      Aluminium + ISO 5817 (gilt für Stahl, für Alu: ISO 10042).
#
# Die Werkstoffdatenbank ist bewusst kompakt und konservativ: nur eindeutige
# Fälle führen zu einem Fehler, Unsicheres wird als "Prüfen" (warning) gemeldet.



import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .regeln import RULES_DIR, CheckContext, rules_files

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
    max_hrc: float | None = None   # erreichbare Oberflächenhärte (HRC)
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
                    max_hrc=(float(e["max_hrc"]) if e.get("max_hrc") else None),
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


# Gattungsbegriffe für eloxierfähige Werkstoffe (ohne Legierungsangabe).
RE_ALU_TEXT = re.compile(r"alumin(?:i)?um|\baluminium\b|\btitan(?:ium)?\b",
                         re.IGNORECASE)


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
        # Auf Zeichnungen mit mehreren Werkstoffen (Baugruppen, Einsätze)
        # gehört das Eloxieren oft zu einem anderen Teil als dem
        # Hauptwerkstoff – dann ist es kein Widerspruch.
        # Auch die bloße Nennung („Aluminum insert") zählt hier als Beleg –
        # für den Widerspruch genügt sie, für MAT.MISSING nicht (eine
        # Gattung ohne Legierung ist keine beschaffbare Angabe).
        eloxierbar = (any(h.material.category in ("alu", "titan") for h in hits)
                      or bool(RE_ALU_TEXT.search(ctx.pdf.full_text())))
        if anod and not eloxierbar and primary.category not in ("alu", "titan"):
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


# ======================================================================
# process_checks
# ======================================================================
# Verfahrensspezifische Vollständigkeitsprüfungen.
#
# Prüft je erkanntem Fertigungsverfahren, ob die dafür zwingenden Angaben auf
# der Zeichnung stehen. Grundlage: Fertigungs- und Schweißpraxis (ISO 2553,
# ISO 9692, VDG-Merkblatt K 200, Blech-Konstruktionsrichtlinien).
#
#   WELD.NO_SIZE      Schweißsymbolik ohne Nahtdicke (a-/z-Maß)
#   WELD.AZ_MIXED     a- und z-Maße gemischt – teuerster Lesefehler der Praxis
#   WELD.NO_PREP      Stumpfnaht ohne Angabe der Nahtvorbereitung (ISO 9692)
#   CAST.NO_DRAFT     Gussteil ohne Formschrägen-Angabe (ISO 10135/DIN EN 12890)
#   CAST.NO_RMA       Gussteil mit Bearbeitung, aber ohne Bearbeitungszugabe
#   SHEET.NO_THICK    Blech-/Biegeteil ohne Blechdickenangabe
#   SHEET.NO_RADIUS   Abkantung ohne Biegeradius
#   HT.NO_HARDNESS    Wärmebehandlung ohne Härtewert (DIN 6773)
#   HT.NO_DEPTH       Randschichthärten ohne Einhärtetiefe (Eht/CHD/NHD)
#   HT.HARDNESS_LIMIT Härteforderung über dem, was der Werkstoff hergibt



import re

from .zeichnung import DimKind, DimValue
from .regeln import CheckContext

# --- Schweißen ------------------------------------------------------------
# a-Maß (Nahtdicke) und z-Maß (Schenkellänge) einer Kehlnaht.
RE_WELD_A = re.compile(r"(?<![A-Za-z0-9])a\s?(\d{1,2}(?:[.,]\d)?)\b")
RE_WELD_Z = re.compile(r"(?<![A-Za-z0-9])z\s?(\d{1,2}(?:[.,]\d)?)\b")
# "fillet" heißt auf englischen Zeichnungen meist Eckenradius, nicht
# Kehlnaht – allein ist es kein Schweißbeleg (Kalibriersatz: 21 Fehlalarme).
RE_WELD_CONTEXT = re.compile(
    r"schwei[ßs]|\bweld|\bnaht\b|kehlnaht|fillet\s*weld|weld\s*seam"
    r"|ISO\s*2553|ISO\s*5817",
    re.IGNORECASE)
RE_BUTT_WELD = re.compile(
    r"stumpfnaht|stumpfsto[ßs]|\bV-?naht\b|\bY-?naht\b|\bU-?naht\b"
    r"|\bHV-?naht\b|\bDV-?naht\b|butt\s*weld|groove\s*weld|full\s*pen",
    re.IGNORECASE)
RE_WELD_PREP = re.compile(
    r"ISO\s*9692|nahtvorbereitung|fugenform|wurzel(?:öffnung|spalt)"
    r"|öffnungswinkel|steghöhe|joint\s*preparation|root\s*(?:gap|face)",
    re.IGNORECASE)

# --- Guss -----------------------------------------------------------------
RE_CAST_CONTEXT = re.compile(
    r"\bguss(?:teil|rohteil|stück)?\b|casting|EN[-\s]?GJ|rohteil|sandguss"
    r"|druckguss|kokillenguss", re.IGNORECASE)
RE_DRAFT = re.compile(
    r"formschräge|aushebeschräge|draft\s*angle|entformungsschräge"
    r"|ISO\s*10135|DIN\s*EN\s*12890|\b\d{1,2}\s*°\s*(?:formschräge|draft)",
    re.IGNORECASE)
RE_RMA = re.compile(
    r"bearbeitungszugabe|aufma[ßs]|\bRMA\b|machining\s*allowance"
    r"|zugabe\s*\d|ISO\s*8062-?3", re.IGNORECASE)
RE_MACHINED_SURFACE = re.compile(
    r"bearbeitet|gefräst|gedreht|geschliffen|machined|spanend|\bRa\s*\d"
    r"|\bH[789]\b|\bh[6789]\b", re.IGNORECASE)

# --- Blech ----------------------------------------------------------------
RE_SHEET_CONTEXT = re.compile(
    r"\bblech\b|abgekantet|gekantet|abkanten|kantung|biegeteil|sheet\s*metal"
    r"|laserzuschnitt|lasergeschnitten|\bbend(?:ing)?\b|abwicklung",
    re.IGNORECASE)
RE_SHEET_THICK = re.compile(
    r"blechdicke|blechstärke|materialstärke|\bdicke\s*\d|\bt\s*=\s*\d"
    r"|sheet\s*thickness|thickness\s*\d|\bs\s*=\s*\d", re.IGNORECASE)
RE_BEND_RADIUS = re.compile(
    r"biegeradius|innenradius|\bri\s*=|bend\s*radius|inner\s*radius"
    r"|biegeradien", re.IGNORECASE)
RE_BEND_PRESENT = re.compile(
    r"abgekantet|gekantet|abkanten|kantung|biegeteil|biegewinkel"
    r"|\bbend(?:ing|s)?\b|abwicklung", re.IGNORECASE)


def _find(ctx: CheckContext, regex: re.Pattern):
    for b in ctx.pdf.blocks():
        m = regex.search(b.text)
        if m:
            return m, b.bbox, b.page
    return None


def check_weld_details(ctx: CheckContext) -> None:
    hit = _find(ctx, RE_WELD_CONTEXT)
    if not hit:
        return
    _m, bbox, page = hit
    text = ctx.pdf.full_text()
    a_sizes = RE_WELD_A.findall(text)
    z_sizes = RE_WELD_Z.findall(text)

    if ctx.profile.enabled("WELD.NO_SIZE") and not a_sizes and not z_sizes:
        ctx.add("WELD.NO_SIZE",
                "Schweißangaben ohne Nahtdicke (a-Maß bzw. z-Maß)",
                bbox=bbox, page=page,
                detail="Ohne Nahtdicke ist die Verbindung nicht bemessen – "
                       "a (Nahtdicke) oder z (Schenkellänge) nach ISO 2553 "
                       "angeben.")
    elif ctx.profile.enabled("WELD.AZ_MIXED") and a_sizes and z_sizes:
        ctx.add("WELD.AZ_MIXED",
                f"a- und z-Maße gemischt verwendet (a: {', '.join(a_sizes[:3])}"
                f" / z: {', '.join(z_sizes[:3])})",
                bbox=bbox, page=page,
                detail="a-Maß (Nahtdicke) und z-Maß (Schenkellänge) "
                       "unterscheiden sich um Faktor √2 (~29 %). Gemischte "
                       "Angaben auf einer Zeichnung führen regelmäßig zu "
                       "unterdimensionierten Nähten – einheitlich bemaßen.")

    if ctx.profile.enabled("WELD.NO_PREP"):
        butt = _find(ctx, RE_BUTT_WELD)
        if butt and not _find(ctx, RE_WELD_PREP):
            _bm, bbbox, bpage = butt
            ctx.add("WELD.NO_PREP",
                    "Stumpf-/Fugennaht ohne Angabe der Nahtvorbereitung",
                    bbox=bbbox, page=bpage,
                    detail="Fugenform, Öffnungswinkel und Wurzelspalt nach "
                           "ISO 9692 angeben – sonst entscheidet der "
                           "Lieferant über die Nahtqualität.")


def check_cast_details(ctx: CheckContext) -> None:
    hit = _find(ctx, RE_CAST_CONTEXT)
    if not hit:
        return
    _m, bbox, page = hit
    if ctx.profile.enabled("CAST.NO_DRAFT") and not _find(ctx, RE_DRAFT):
        ctx.add("CAST.NO_DRAFT",
                "Gussteil ohne Angabe von Formschrägen",
                bbox=bbox, page=page,
                detail="Formschrägen sind in Winkelgraden anzugeben "
                       "(DIN EN 12890 / ISO 10135); ohne Angabe legt sie die "
                       "Gießerei fest – mit Folgen für Maße und Gewicht.")
    if (ctx.profile.enabled("CAST.NO_RMA")
            and _find(ctx, RE_MACHINED_SURFACE) and not _find(ctx, RE_RMA)):
        ctx.add("CAST.NO_RMA",
                "Gussteil mit bearbeiteten Flächen, aber ohne "
                "Bearbeitungszugabe (RMA)",
                bbox=bbox, page=page,
                detail="Bearbeitungszugabe nach ISO 8062-3 angeben, sonst ist "
                       "unklar, ob das Rohteil genug Material für die "
                       "Bearbeitung hat.")


def check_sheet_details(ctx: CheckContext, dims: list[DimValue]) -> None:
    hit = _find(ctx, RE_SHEET_CONTEXT)
    if not hit:
        return
    _m, bbox, page = hit
    if ctx.profile.enabled("SHEET.NO_THICK") and not _find(ctx, RE_SHEET_THICK):
        ctx.add("SHEET.NO_THICK",
                "Blech-/Biegeteil ohne ausgewiesene Blechdicke",
                bbox=bbox, page=page,
                detail="Blechdicke explizit angeben (z. B. „Blechdicke 3 mm“ "
                       "oder t = 3) – aus der Ansicht allein ist sie für den "
                       "Zuschnitt nicht eindeutig.")
    if ctx.profile.enabled("SHEET.NO_RADIUS"):
        bend = _find(ctx, RE_BEND_PRESENT)
        has_radius = bool(_find(ctx, RE_BEND_RADIUS)
                          or [d for d in dims if d.kind is DimKind.RADIUS])
        if bend and not has_radius:
            _bm, bbbox, bpage = bend
            ctx.add("SHEET.NO_RADIUS",
                    "Abkantung ohne Angabe des Biegeradius",
                    bbox=bbbox, page=bpage,
                    detail="Innenradius angeben (Faustregel ri ≥ Blechdicke). "
                           "Ohne Angabe wählt der Fertiger das Werkzeug – "
                           "Abwicklung und Endmaße ändern sich dadurch.")


def run_process_checks(ctx: CheckContext, dims: list[DimValue]) -> None:
    check_weld_details(ctx)
    check_cast_details(ctx)
    check_sheet_details(ctx, dims)
    check_heat_treatment(ctx)
    check_hydrogen_embrittlement(ctx)


# --- Wasserstoffversprödung (EN ISO 4042 / EN ISO 9588) -------------------
# Galvanische (elektrolytische) Beschichtungen setzen Wasserstoff frei.
RE_GALVANIC = re.compile(
    r"galvanisch\s*(?:verzinkt|vernickelt|verchromt)?|elektrolytisch"
    r"|Zn/?Ni|zink[-\s]?nickel|vercadmiert|Cd\s*besch"
    r"|electroplat|zinc\s*plated|ISO\s*4042|ISO\s*2081|ISO\s*19598",
    re.IGNORECASE)
# Hinweis auf die vorgeschriebene Entsprödung.
RE_DEEMBRITTLE = re.compile(
    r"entspröd|wasserstoffarm|wasserstoffvers|entsprödungsglüh|tempern"
    r"|bak(?:e|ing|en)|hydrogen\s*(?:relief|embrittle)|ISO\s*9588"
    r"|ISO\s*15330", re.IGNORECASE)
# Festigkeitsklassen und Härten, ab denen entsprödet werden muss.
RE_HIGH_STRENGTH_CLASS = re.compile(
    r"(?:10\.9|12\.9|14\.9)|festigkeitsklasse\s*(?:10|12|14)",
    re.IGNORECASE)


def check_hydrogen_embrittlement(ctx: CheckContext) -> None:
    """Galvanische Beschichtung auf hochfestem Stahl ohne Entsprödung.

    Nach EN ISO 4042 müssen Teile mit einer Zugfestigkeit ab 1000 MPa
    (bzw. Härte ab 320 HV / 32 HRC) und Festigkeitsklassen ab 10.9 nach dem
    galvanischen Beschichten wasserstoffarm geglüht werden – sonst brechen
    sie verzögert und ohne Vorankündigung. Auf Zeichnungen fehlt die
    Forderung regelmäßig, weil sie als „Sache des Beschichters" gilt.
    """
    if not ctx.profile.enabled("COAT.EMBRITTLEMENT"):
        return
    hit = _find(ctx, RE_GALVANIC)
    if hit is None or _find(ctx, RE_DEEMBRITTLE):
        return
    _m, bbox, page = hit
    reason = _high_strength_reason(ctx)
    if not reason:
        return
    ctx.add("COAT.EMBRITTLEMENT",
            f"Galvanische Beschichtung an hochfestem Bauteil ({reason}) ohne "
            f"geforderte Entsprödung",
            bbox=bbox, page=page,
            detail="EN ISO 4042 verlangt ab 1000 MPa bzw. 320 HV eine "
                   "Wasserstoffarmglühung (typisch 190–230 °C, ≥ 4 h, "
                   "innerhalb von 4 h nach dem Beschichten); die Wirksamkeit "
                   "wird nach EN ISO 15330 nachgewiesen. Ohne diese Angabe "
                   "drohen verzögerte Sprödbrüche. Alternativ mechanisch "
                   "beschichten oder eine Zinklamellenbeschichtung "
                   "(ISO 10683) vorschreiben.")


def _high_strength_reason(ctx: CheckContext) -> str:
    """Begründung, warum das Teil als hochfest gilt ("" = ist es nicht)."""
    text = ctx.pdf.full_text()
    m = RE_HIGH_STRENGTH_CLASS.search(text)
    if m:
        return f"Festigkeitsklasse {m.group(0)}"
    for m in RE_HARDNESS_HRC.finditer(text):
        try:
            if float(m.group(1).replace(",", ".")) >= 32:
                return f"{m.group(0).strip()}"
        except ValueError:
            continue
    for m in RE_HARDNESS_HV.finditer(text):
        try:
            if float(m.group(1)) >= 320:
                return f"{m.group(0).strip()}"
        except ValueError:
            continue
    for m in RE_STRENGTH.finditer(text):
        for group in m.groups():
            try:
                if group and float(str(group).replace(",", ".")) >= 1000:
                    return f"{m.group(0).strip()}"
            except ValueError:
                continue
    return ""


# --- Wärmebehandlung (DIN 6773) -------------------------------------------
RE_HARDNESS_HRC = re.compile(r"(\d{2}(?:[.,]\d)?)\s*[-–+±]?\s*(?:\d{1,2})?\s*HRC",
                             re.IGNORECASE)
RE_HARDNESS_HV = re.compile(r"(\d{3,4})\s*HV\s*\d*", re.IGNORECASE)
RE_HARDNESS_ANY = re.compile(r"\bHRC\b|\bHV\s*\d|\bHB\b|härte(?!n)|hardness",
                             re.IGNORECASE)
RE_CASE_DEPTH = re.compile(
    r"\bEht\b|\bCHD\b|\bNHD\b|\bSHD\b|einhärt(?:e|ungs)tiefe|nitrierhärtetiefe"
    r"|case\s*depth|einsatztiefe|\bRht\b", re.IGNORECASE)
RE_SURFACE_HT = re.compile(
    r"einsatzgehärtet|einsatzhärten|aufgekohlt|carburi[sz]|nitrier|nitrid"
    r"|randschichtgehärtet|induktivgehärtet|induction\s*harden|case\s*harden"
    r"|flammgehärtet", re.IGNORECASE)
# Genormter Lieferzustand im Werkstoffnamen (+QT, +N, +A …): Wärmebehandlung
# und Festigkeit sind damit normativ festgelegt (z. B. EN 10083) – eine
# separate Härteangabe ist dann NICHT erforderlich.
RE_DELIVERY_STATE = re.compile(
    r"\+\s*(?:QT|AT|NT|AR|N|A|C|M|P|SR|U)\b")
RE_STRENGTH = re.compile(
    r"\b\d{3,4}\s*(?:N/mm²|N/mm2|MPa)\b|\bRm\s*[≥>=]|\bRe(?:H|L)?\s*[≥>=]",
    re.IGNORECASE)
RE_HT_PROCESS = re.compile(
    r"gehärtet|härten|vergütet|vergüten|hardened|quenched|tempered"
    r"|einsatzgehärtet|nitriert", re.IGNORECASE)


def check_heat_treatment(ctx: CheckContext) -> None:
    """Härteangaben auf Vollständigkeit und Plausibilität prüfen (DIN 6773)."""
    pass  # (im selben Modul)

    ht = _find(ctx, RE_HT_PROCESS)
    if not ht:
        return
    _m, bbox, page = ht
    text = ctx.pdf.full_text()

    # 1) Härteverfahren ohne Härtewert
    if (ctx.profile.enabled("HT.NO_HARDNESS")
            and not RE_HARDNESS_ANY.search(text)
            and not RE_DELIVERY_STATE.search(text)
            and not RE_STRENGTH.search(text)):
        ctx.add("HT.NO_HARDNESS",
                "Wärmebehandlung angegeben, aber kein Härtewert",
                bbox=bbox, page=page,
                detail="Nach DIN 6773 gehören Oberflächenhärte (HRC/HV) und "
                       "Toleranz zur Angabe – sonst ist das Ergebnis nicht "
                       "prüfbar.")

    # 2) Randschichtverfahren ohne Einhärtetiefe
    surface = _find(ctx, RE_SURFACE_HT)
    if (ctx.profile.enabled("HT.NO_DEPTH") and surface
            and not RE_CASE_DEPTH.search(text)):
        _sm, sbbox, spage = surface
        ctx.add("HT.NO_DEPTH",
                "Randschichthärten ohne Angabe der Einhärtetiefe",
                bbox=sbbox, page=spage,
                detail="Einhärtungstiefe (Eht/CHD bzw. NHD beim Nitrieren) "
                       "mit Grenzhärte angeben – ohne sie ist die Randschicht "
                       "nicht spezifiziert (DIN 6773 / ISO 15787).")

    # 3) Härtewert über dem, was der Werkstoff hergibt
    if not ctx.profile.enabled("HT.HARDNESS_LIMIT"):
        return
    hits = find_materials(ctx)
    material = next((h.material for h in hits if h.material.max_hrc), None)
    if material is None:
        return
    values = [float(v.replace(",", ".")) for v in RE_HARDNESS_HRC.findall(text)]
    if not values:
        return
    reserve = float(ctx.profile.params.get("hardness_reserve_hrc", 2))
    highest = max(values)
    if highest > material.max_hrc + reserve:
        ctx.add("HT.HARDNESS_LIMIT",
                f"Härteforderung {highest:g} HRC über dem für {material.name} "
                f"erreichbaren Wert (ca. {material.max_hrc:g} HRC)",
                bbox=bbox, page=page,
                detail="Entweder ist der Werkstoff für die geforderte Härte "
                       "ungeeignet oder die Härteangabe ist zu hoch – "
                       "Werkstoff oder Anforderung anpassen.")


# ======================================================================
# mass_checks
# ======================================================================
# Plausibilitätsprüfung der Gewichtsangabe – auch ohne STEP-Datei.
#
# Der Masseabgleich gegen das STEP-Modell (`geometry_checks.check_mass`) ist
# die schärfste Prüfung, setzt aber ein STEP voraus. Weil ein großer Teil der
# Pakete nur ein PDF enthält, prüft dieses Modul die Gewichtsangabe allein
# gegen die Zeichnung:
#
#   MASS.IMPOSSIBLE  Das Teil wäre schwerer als ein VOLLER Quader seiner
#                    Hüllmaße. Physikalisch unmöglich – klassische Ursachen:
#                    Einheit vertauscht (g/kg), Komma verrutscht, Gewicht aus
#                    einer anderen Variante übernommen, falscher Werkstoff.
#   MASS.TOO_LIGHT   Das Teil wäre fast nur Luft (Füllgrad < 1 %). Bei Blech-
#                    und Schweißkonstruktionen möglich, sonst verdächtig.
#   MASS.DENSITY_HINT Die Gewichtsangabe passt rechnerisch zu einem ANDEREN
#                    Werkstoff als dem angegebenen (Volumen aus dem STEP).
#                    Findet den häufigsten Fall „Schriftfeld kopiert".
#
# Grundgedanke der Unmöglichkeitsprüfung:
#
#     m = ρ · V_Teil   und   V_Teil ≤ V_Hüllquader
#     =>  ρ_rechnerisch = m / V_Hüllquader ≤ ρ_Werkstoff
#
# Weil die Hüllmaße aus den größten Zeichnungsmaßen geschätzt werden, ist der
# Quader in aller Regel zu GROSS – das Urteil „unmöglich" ist damit auf der
# sicheren Seite. Zusätzlich wird erst ab einem deutlichen Faktor gemeldet.



import logging

from .kern import Severity
from .zeichnung import DimValue, estimate_envelope
from .zeichnung import extract_weight_kg
from .regeln import CheckContext


# Verhältnis rechnerische Dichte / Werkstoffdichte, ab dem gemeldet wird.
DEFAULT_IMPOSSIBLE_FACTOR = 1.3     # 30 % Reserve für grobe Hüllmaßschätzung
DEFAULT_MIN_FILL = 0.01             # Füllgrad, unter dem es verdächtig wird
# Typische Zahlendreher: Faktor zwischen Angabe und Rechnung.
UNIT_FACTORS = {1000.0: "g statt kg", 100.0: "Komma zwei Stellen verrutscht",
                10.0: "Komma eine Stelle verrutscht"}


def check_mass_plausibility(ctx: CheckContext, dims: list[DimValue]) -> str:
    """Gewichtsangabe gegen die Hüllmaße der Zeichnung prüfen.

    Rückgabe: Kurztext für die Excel-Vergleichswerte ("" wenn nicht prüfbar).
    """
    if not (ctx.profile.enabled("MASS.IMPOSSIBLE")
            or ctx.profile.enabled("MASS.TOO_LIGHT")):
        return ""
    drawing_kg = extract_weight_kg(ctx.pdf)
    if drawing_kg is None:
        return ""
    density = _declared_density(ctx)
    if density is None:
        return ""
    box_cm3 = _envelope_volume_cm3(dims)
    if box_cm3 is None:
        return ""

    max_kg = box_cm3 * density / 1000.0        # g/cm³ · cm³ = g -> kg
    fill = drawing_kg / max_kg if max_kg else 0.0
    summary = (f"Masse-Plausibilität: {drawing_kg:.2f} kg, Hüllquader "
               f"{box_cm3:.0f} cm³ → Füllgrad {fill * 100:.0f} %")

    factor = float(ctx.profile.params.get("mass_impossible_factor",
                                          DEFAULT_IMPOSSIBLE_FACTOR))
    if fill > factor and ctx.profile.enabled("MASS.IMPOSSIBLE"):
        ctx.add("MASS.IMPOSSIBLE",
                f"Gewichtsangabe unmöglich: {drawing_kg:.2f} kg bei Hüllmaßen "
                f"{_envelope_text(dims)} – ein VOLLER Block aus diesem "
                f"Werkstoff wöge nur {max_kg:.2f} kg",
                detail=_explain(drawing_kg, max_kg, density, box_cm3))
    elif (fill < float(ctx.profile.params.get("mass_min_fill", DEFAULT_MIN_FILL))
          and ctx.profile.enabled("MASS.TOO_LIGHT")):
        ctx.add("MASS.TOO_LIGHT",
                f"Gewichtsangabe sehr klein: {drawing_kg:.3f} kg entspricht "
                f"{fill * 100:.1f} % des Hüllquaders ({max_kg:.1f} kg voll)",
                severity=ctx.profile.severity("MASS.TOO_LIGHT",
                                              Severity.WARNING),
                detail="Bei dünnen Blechen und Schweißrahmen möglich. Sonst "
                       "prüfen, ob die Einheit stimmt (g statt kg) oder das "
                       "Gewicht von einer kleineren Variante stammt.")
    return summary


def check_density_hint(ctx: CheckContext, model_volume_mm3: float) -> None:
    """Passt die Gewichtsangabe rechnerisch zu einem anderen Werkstoff?

    Wird nur mit STEP aufgerufen (exaktes Volumen). Der Hinweis ist die
    Diagnose zur Massenabweichung: „Angabe passt zu Stahl, angegeben ist
    Aluminium" – der Klassiker beim kopierten Schriftfeld.
    """
    if not ctx.profile.enabled("MASS.DENSITY_HINT") or model_volume_mm3 <= 0:
        return
    drawing_kg = extract_weight_kg(ctx.pdf)
    if drawing_kg is None:
        return
    declared = _declared_material(ctx)
    if declared is None or not declared.density:
        return
    volume_cm3 = model_volume_mm3 / 1000.0
    implied = drawing_kg * 1000.0 / volume_cm3      # g/cm³
    if abs(implied - declared.density) / declared.density <= 0.10:
        return                                      # passt zum Werkstoff

    match = _closest_material(implied, exclude=declared.name)
    if match is None:
        return
    ctx.add("MASS.DENSITY_HINT",
            f"Gewichtsangabe passt nicht zu {declared.name}: rechnerisch "
            f"{implied:.1f} g/cm³ – das entspricht {match.name} "
            f"({match.density} g/cm³)",
            detail=f"{drawing_kg:.2f} kg auf {volume_cm3:.0f} cm³ "
                   f"Modellvolumen. Häufige Ursache: Schriftfeld aus einer "
                   f"anderen Zeichnung übernommen, Werkstoff geändert ohne "
                   f"das Gewicht neu zu rechnen, oder falsche Variante im "
                   f"STEP. Erwartet für {declared.name}: "
                   f"{volume_cm3 * declared.density / 1000:.2f} kg.")


# ---------------------------------------------------------------- Intern
def _declared_material(ctx: CheckContext):
    hits = [h.material for h in find_materials(ctx) if h.material.density]
    return hits[0] if hits else None


def _declared_density(ctx: CheckContext) -> float | None:
    mat = _declared_material(ctx)
    return mat.density if mat else None


def _envelope_volume_cm3(dims: list[DimValue]) -> float | None:
    """Volumen des geschätzten Hüllquaders in cm³.

    Genutzt werden die drei größten unterschiedlichen Maße. Fehlt eine
    dritte Kante (typisch bei Wellen: nur Länge und Durchmesser bemaßt),
    wird die zweitgrößte doppelt verwendet – der Quader bleibt damit eine
    Obergrenze für das tatsächliche Bauteilvolumen.
    """
    env = estimate_envelope(dims, top_n=3)
    if len(env) < 2:
        return None
    a, b = env[0], env[1]
    c = env[2] if len(env) >= 3 else b
    volume = a * b * c / 1000.0
    return volume if volume > 0 else None


def _envelope_text(dims: list[DimValue]) -> str:
    env = estimate_envelope(dims, top_n=3)
    return "×".join(f"{v:g}" for v in env) + " mm"


def _explain(drawing_kg: float, max_kg: float, density: float,
             box_cm3: float) -> str:
    ratio = drawing_kg / max_kg if max_kg else 0.0
    hint = ""
    for factor, text in UNIT_FACTORS.items():
        if abs(ratio - factor) / factor < 0.35:
            hint = f" Der Faktor ≈ {factor:g} deutet auf {text} hin."
            break
    return (f"Hüllquader {box_cm3:.0f} cm³ × {density} g/cm³ = {max_kg:.2f} kg "
            f"als absolute Obergrenze; angegeben sind {drawing_kg:.2f} kg "
            f"({ratio:.1f}-faches).{hint} Die Hüllmaße stammen aus den "
            f"größten Zeichnungsmaßen und sind eher zu groß geschätzt – die "
            f"Angabe ist damit sicher zu hoch.")


def _closest_material(implied: float, exclude: str):
    """Werkstoff, dessen Dichte am besten zur Rechnung passt (±8 %)."""
    best = None
    best_dev = 0.08
    for mat in MATERIALS:
        if not mat.density or mat.name == exclude:
            continue
        dev = abs(mat.density - implied) / mat.density
        if dev < best_dev:
            best, best_dev = mat, dev
    return best


# ======================================================================
# purchasing_checks
# ======================================================================
# Prüfung aus Sicht des internationalen Einkaufs.
#
# Die Zeichnung muss für einen Lieferanten ausreichen, der weder im Haus
# sitzt noch die Historie des Teils kennt. Geprüft wird deshalb nicht nur die
# technische Richtigkeit, sondern die Anfragereife:
#
#   PUR.VAGUE_SPEC   Formulierungen ohne prüfbaren Inhalt („ca. 20", „nach
#                    Absprache", „sauber entgraten", „TBD"). Sie erzeugen
#                    Rückfragen, Nachträge und Streit bei der Abnahme.
#   PUR.INTERNAL_NORM Verweis auf Werk-/Konzernnormen, die ein externer
#                    Lieferant nicht beziehen kann. Sie müssen der Anfrage
#                    als Dokument beiliegen.
#   PUR.STOCK_SIZE   Blechdicke oder Rundmaterial außerhalb der gängigen
#                    Vorzugsmaße. Das Teil muss dann aus dem nächstgrößeren
#                    Halbzeug herausgearbeitet werden – teurer, längere
#                    Lieferzeit, oft ohne konstruktiven Grund.
#
# Das Wissen steht in `rules/beschaffung*.yaml` und ist ohne Codeänderung
# erweiterbar.



import logging
import re

import yaml

from .zeichnung import DimValue
from .regeln import CheckContext, rules_files



def _load_knowledge() -> dict:
    """Alle beschaffung*.yaml einsammeln (mitgeliefert + externe Ordner)."""
    vage: list[tuple[re.Pattern, str]] = []
    hausnormen: list[tuple[re.Pattern, str]] = []
    halbzeuge: dict[str, list[float]] = {}
    for f in rules_files("beschaffung*.yaml"):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            log.error("Beschaffungs-Wissenspaket %s nicht lesbar: %s", f, exc)
            continue
        for key, target in (("vage", vage), ("hausnormen", hausnormen)):
            for entry in data.get(key, []) or []:
                try:
                    target.append((re.compile(entry["pattern"], re.IGNORECASE),
                                   entry["message"]))
                except (KeyError, TypeError, re.error) as exc:
                    log.error("Eintrag in %s (%s) fehlerhaft: %s", f, key, exc)
        for key, values in (data.get("halbzeuge") or {}).items():
            try:
                halbzeuge.setdefault(key, []).extend(float(v) for v in values)
            except (TypeError, ValueError):
                log.error("Halbzeugliste %r in %s fehlerhaft", key, f)
    return {"vage": vage, "hausnormen": hausnormen, "halbzeuge": halbzeuge}


KNOWLEDGE = _load_knowledge()

RE_SHEET_THICK_VALUE = re.compile(
    r"(?:blechdicke|blechstärke|materialstärke|sheet\s*thickness"
    r"|thickness|dicke|\bt|\bs)\s*[:=]?\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:mm)?",
    re.IGNORECASE)
RE_ROUND_STOCK = re.compile(
    r"(?:rundstahl|rundmaterial|blankstahl|round\s*bar|stangenmaterial)"
    r"[^\n]{0,20}?(\d{1,3}(?:[.,]\d{1,2})?)", re.IGNORECASE)


def run_purchasing_checks(ctx: CheckContext, dims: list[DimValue]) -> None:
    check_vague_specs(ctx)
    check_internal_norms(ctx)
    check_stock_sizes(ctx, dims)


def check_vague_specs(ctx: CheckContext) -> None:
    """Unbestimmte Formulierungen melden – je Muster höchstens einmal."""
    if not ctx.profile.enabled("PUR.VAGUE_SPEC"):
        return
    limit = int(ctx.profile.rule_param("PUR.VAGUE_SPEC", "max_findings", 4))
    shown = 0
    for regex, message in KNOWLEDGE["vage"]:
        hit = _first_hit(ctx, regex)
        if hit is None:
            continue
        matched, bbox, page = hit
        shown += 1
        if shown > limit:
            continue
        ctx.add("PUR.VAGUE_SPEC",
                f"Unbestimmte Angabe „{matched.strip()}“: {message}",
                bbox=bbox, page=page,
                detail="Aus Sicht eines auswärtigen Lieferanten nicht "
                       "kalkulierbar und bei der Abnahme nicht prüfbar. "
                       "Anforderung mit Zahlenwert oder Norm angeben.")
    if shown > limit:
        ctx.add("PUR.VAGUE_SPEC",
                f"… und {shown - limit} weitere unbestimmte Angaben",
                detail="Vollständige Liste im Regelkatalog "
                       "(rules/beschaffung.yaml).")


def check_internal_norms(ctx: CheckContext) -> None:
    """Verweise auf nicht öffentlich beziehbare Normen melden."""
    if not ctx.profile.enabled("PUR.INTERNAL_NORM"):
        return
    seen: set[str] = set()
    for regex, message in KNOWLEDGE["hausnormen"]:
        hit = _first_hit(ctx, regex)
        if hit is None:
            continue
        matched, bbox, page = hit
        key = matched.strip().upper()
        if key in seen:
            continue
        seen.add(key)
        ctx.add("PUR.INTERNAL_NORM",
                f"Verweis auf interne Norm „{matched.strip()}“: {message}",
                bbox=bbox, page=page,
                detail="Der Anfrage beilegen oder durch eine öffentliche "
                       "Norm ersetzen – sonst liefert jeder Lieferant nach "
                       "eigener Auslegung.")


def check_stock_sizes(ctx: CheckContext, dims: list[DimValue]) -> None:
    """Blechdicke/Rundmaterial gegen die Vorzugsmaße prüfen."""
    if not ctx.profile.enabled("PUR.STOCK_SIZE"):
        return
    sheet = KNOWLEDGE["halbzeuge"].get("blech") or []
    if not sheet:
        return
    text = ctx.pdf.full_text()
    for m in RE_SHEET_THICK_VALUE.finditer(text):
        try:
            value = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        if not 0.3 <= value <= 120:
            continue
        if _matches_stock(value, sheet):
            continue
        nearest = min(sheet, key=lambda s: abs(s - value))
        ctx.add("PUR.STOCK_SIZE",
                f"Blechdicke {value:g} mm ist kein Vorzugsmaß "
                f"(nächstes Lagermaß {nearest:g} mm)",
                detail="Ein Sondermaß bedeutet Mindestabnahmemengen, längere "
                       "Lieferzeit oder Herausarbeiten aus dickerem Material. "
                       "Wenn es keinen funktionalen Grund gibt: auf das "
                       "Lagermaß gehen. Vorzugsmaße pflegbar in "
                       "rules/beschaffung.yaml.")
        break       # eine Blechmeldung je Zeichnung genügt

    _check_round_stock(ctx, text)


def _check_round_stock(ctx: CheckContext, text: str) -> None:
    """Ausdrücklich genanntes Rundmaterial gegen die Lagerdurchmesser prüfen.

    Bewusst nur bei ausgeschriebenem Halbzeug („Rundstahl ⌀37") – jeder
    beliebige Durchmesser auf der Zeichnung wäre ein Maß am Fertigteil und
    sagt nichts über das Halbzeug aus.
    """
    series = KNOWLEDGE["halbzeuge"].get("rund") or []
    if not series:
        return
    for m in RE_ROUND_STOCK.finditer(text):
        try:
            value = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        if not 3 <= value <= 300 or _matches_stock(value, series, tol=0.2):
            continue
        nearest = min(series, key=lambda s: abs(s - value))
        ctx.add("PUR.STOCK_SIZE",
                f"Rundmaterial ⌀{value:g} mm ist kein Lagermaß "
                f"(nächstes {nearest:g} mm)",
                detail="Sonderdurchmesser müssen aus dem nächstgrößeren "
                       "Stangenmaterial gedreht werden – mehr Zerspanung, "
                       "höherer Preis, längere Beschaffung.")
        return


def _matches_stock(value: float, series: list[float],
                   tol: float = 0.05) -> bool:
    return any(abs(value - s) <= tol for s in series)


def _first_hit(ctx: CheckContext, regex: re.Pattern):
    """Erster Treffer mit Fundstelle (für die Markierung im Bild)."""
    for block in ctx.pdf.blocks():
        m = regex.search(block.text)
        if m:
            return m.group(0), block.bbox, block.page
    return None
