"""Fachliche Zeichnungs-Checks nach allgemeinen Normen (Sicht: internationaler Einkauf).

Regelgruppen (Codes siehe rules/profiles.yaml):
  TB.*   Schriftfeld (ISO 7200)
  GT.*   Allgemeintoleranzen / Tolerierungsgrundsatz (ISO 2768, ISO 22081, ISO 8015)
  GPS.*  Form- und Lagetolerierung (ISO 1101)
  SURF.* Oberflächen und Kanten (ISO 21920 / ISO 1302, ISO 13715)
  VIEW.* Darstellung (Projektionsmethode, Einheit)
  WELD.* / CAST.*  Kontextregeln für Schweiß- und Gussteile (ISO 2553/5817, ISO 8062)
  CONS.* Konsistenz zur Anfrage (Materialnummer)

Prinzip: Regeln, die auf der Zeichnung nicht sicher entscheidbar sind, melden
"nicht nachweisbar" (Severity aus dem Profil, i. d. R. warning) statt hart "fehlt".
"""
from __future__ import annotations

import re

from ..core.models import BBox, Severity
from .base import CheckContext

# ---------------------------------------------------------------- Normmuster
RE_ISO2768 = re.compile(r"ISO\s*2768\s*[-–]?\s*([a-zA-Z]{1,2})?", re.IGNORECASE)
RE_ISO22081 = re.compile(r"ISO\s*22081", re.IGNORECASE)
RE_ISO8015 = re.compile(r"ISO\s*8015", re.IGNORECASE)
RE_ISO13715 = re.compile(r"ISO\s*13715", re.IGNORECASE)
RE_SURF_NORM = re.compile(r"ISO\s*(21920|1302)", re.IGNORECASE)
RE_ROUGHNESS = re.compile(r"\bR[az]\s*\d+(?:[.,]\d+)?", re.IGNORECASE)
RE_ISO5817 = re.compile(r"ISO\s*5817\s*[-–]?\s*([BCD])?", re.IGNORECASE)
RE_ISO2553 = re.compile(r"ISO\s*2553", re.IGNORECASE)
RE_ISO8062 = re.compile(r"ISO\s*8062(?:\s*[-–]?\s*3)?", re.IGNORECASE)
RE_DCTG = re.compile(r"\b[DG]CTG?\s*\d{1,2}\b", re.IGNORECASE)
RE_CT_GRADE = re.compile(r"\bCT\s*\d{1,2}\b")
RE_PROJECTION = re.compile(
    r"(first\s+angle|third\s+angle|1st\s+angle|3rd\s+angle|projektionsmethode\s*[13]?"
    r"|projection\s+method)", re.IGNORECASE)
RE_UNIT_MM = re.compile(r"(dimensions?\s+(?:are\s+)?in\s+mm|maße\s+in\s+mm"
                        r"|angaben\s+in\s+mm|unit\s*s?\s*:?\s*(?:mm|inch)"
                        r"|\bin\s+millimet|dimensions?\s+(?:are\s+)?in\s+inch)",
                        re.IGNORECASE)
# ASME-Welt: Toleranzblock im Schriftfeld + Y14.5 als Tolerierungsgrundsatz.
RE_ASME_Y145 = re.compile(r"ASME\s*Y\s*14\.5", re.IGNORECASE)
RE_ASME_TOLBLOCK = re.compile(
    r"TOLERANCES?\s*[:\s].{0,200}?(?:DECIMAL|±|ANGULAR)"
    r"|TOLERANCES?\s+WITHIN\s*[±]?\s*\d"   # "TOLERANCES WITHIN 0.1"
    r"|\.X{1,3}\s*(?:±|=)"                 # Toleranzzeilen der Form .X± / .XX±
    r"|X\.X{1,3}\s*(?:±|=)",
    re.IGNORECASE | re.DOTALL)
# Kantenzustand als Freitext (statt ISO 13715).
RE_EDGE_TEXT = re.compile(
    r"(break\s+all\s+(?:sharp\s+)?edges|remove\s+all\s+burrs"
    r"|burrs?\s+and\s+sharp\s+edges|deburr|kanten\s+gebrochen"
    r"|kanten\s+entgratet|gratfrei|scharfe\s+kanten\s+(?:brechen|gebrochen))",
    re.IGNORECASE)
# Oberflächenangabe als Freitext.
RE_SURF_TEXT = re.compile(
    r"(surface\s+(?:roughness|finish)|finish\s+all\s+faces"
    r"|\d+\s*µ?in\b|microinch|\bRMS\b)", re.IGNORECASE)
# GD&T-Symbole (Unicode) – Positions-/Form-/Lauf-Toleranzen.
GDT_POSITIONAL = "⌖◎⌯∥⊥∠↗⌰"      # brauchen einen Bezug
GDT_FORM = "⏤⏥○⌭⌒"               # Formtoleranzen: dürfen KEINEN Bezug haben
GDT_ANY = GDT_POSITIONAL + GDT_FORM
# Widersprüchliche GD&T: Formtoleranz (Ebenheit/Geradheit/Rundheit/…)
# mit Bezugsbuchstaben dahinter.
RE_FORM_WITH_DATUM = re.compile(
    rf"[{GDT_FORM}]\s*⌀?\s*\d+(?:[.,]\d+)?\s+[A-Z](?:[-|][A-Z])?\b")
# In ASME Y14.5-2018 gestrichene, messtechnisch problematische Symbole.
RE_DEPRECATED_GDT = re.compile(r"[◎⌯]")
# Stückliste / Positionsballone
RE_BOM_HEADER = re.compile(
    r"stückliste|parts?\s*list|bill\s+of\s+materials?"
    r"|\b(?:pos\.?|item)\b.{0,60}?\b(?:qty|quantity|stück|menge|anzahl)\b"
    r"|\b(?:qty|quantity)\b.{0,60}?\b(?:pos\.?|item)\b",
    re.IGNORECASE | re.DOTALL)
RE_BALLOON_NUM = re.compile(r"^\d{1,2}$")
RE_DATUM = re.compile(r"^[A-Z]$|^\[?[A-Z](?:[-|][A-Z])?\]?$")

WELD_CONTEXT = re.compile(r"schwei|weld|\bwps\b|naht|fillet|seam|a\d+\s*[▲△]?",
                          re.IGNORECASE)
CAST_CONTEXT = re.compile(r"\bguss|gussteil|casting|\bcast\b|EN[-\s]?GJ[SLMV]"
                          r"|\bGG[-\s]?\d\d|\bGGG[-\s]?\d\d|rohteil|formschräge"
                          r"|draft\s+angle", re.IGNORECASE)


def _find(ctx: CheckContext, regex: re.Pattern) -> tuple[re.Match, BBox | None, int] | None:
    """Erster Regex-Treffer über alle Textblöcke, mit Blockposition."""
    for block in ctx.pdf.blocks():
        m = regex.search(block.text)
        if m:
            return m, block.bbox, block.page
    return None

def _has_keyword(ctx: CheckContext, keywords: list[str]) -> bool:
    # Whitespace normalisieren: CAD-Textlayer brechen Labels oft mitten im
    # Wortpaar um ("DWG.\nNO.").
    text = " ".join(ctx.pdf.full_text().lower().split())
    return any(" ".join(k.lower().split()) in text for k in keywords)


# ------------------------------------------------------------ Schriftfeld
TB_RULES = ["TB.DRAWNO", "TB.MATERIAL", "TB.SCALE", "TB.WEIGHT",
            "TB.REVISION", "TB.APPROVAL"]
TB_LABEL = {
    "TB.DRAWNO": "Zeichnungsnummer",
    "TB.MATERIAL": "Werkstoffangabe",
    "TB.SCALE": "Maßstab",
    "TB.WEIGHT": "Gewichtsangabe",
    "TB.REVISION": "Änderungsindex/Revision",
    "TB.APPROVAL": "Prüf-/Freigabevermerk",
}


def check_title_block(ctx: CheckContext) -> None:
    for code in TB_RULES:
        if not ctx.profile.enabled(code):
            continue
        keywords = ctx.profile.rule_param(code, "keywords", [])
        if not _has_keyword(ctx, keywords):
            ctx.add(code,
                    f"Schriftfeld: {TB_LABEL[code]} nicht nachweisbar (ISO 7200)",
                    detail="Gesucht wurde nach: " + ", ".join(keywords))


# ------------------------------------------------------------- Toleranzen
def check_general_tolerances(ctx: CheckContext) -> None:
    if ctx.profile.enabled("GT.GENERAL_TOL"):
        hit2768 = _find(ctx, RE_ISO2768)
        hit22081 = _find(ctx, RE_ISO22081)
        asme_block = RE_ASME_TOLBLOCK.search(ctx.pdf.full_text())
        if not hit2768 and not hit22081 and not asme_block:
            ctx.add("GT.GENERAL_TOL",
                    "Keine Allgemeintoleranzangabe gefunden (ISO 2768/ISO 22081 "
                    "bzw. ASME-Toleranzblock)",
                    detail="Ohne Allgemeintoleranzen sind unbemaßte Toleranzen "
                           "für den Lieferanten nicht definiert.")
        elif hit2768 and not hit2768[0].group(1):
            m, bbox, page = hit2768
            ctx.add("GT.GENERAL_TOL",
                    "ISO 2768 ohne Toleranzklasse angegeben (z. B. „ISO 2768-mK“)",
                    severity=ctx.profile.severity("GT.GENERAL_TOL"),
                    bbox=bbox, page=page)
    if (ctx.profile.enabled("GT.PRINCIPLE")
            and not _find(ctx, RE_ISO8015) and not _find(ctx, RE_ASME_Y145)):
        ctx.add("GT.PRINCIPLE",
                "Tolerierungsgrundsatz nicht nachweisbar (ISO 8015 bzw. "
                "ASME Y14.5)",
                detail="International uneinheitliche Default-Auslegung "
                       "(ISO vs. ASME) – Angabe empfohlen.")


def check_gps_datums(ctx: CheckContext) -> None:
    """Lagetoleranz-Symbole vorhanden, aber keine Bezugsbuchstaben erkennbar."""
    if not ctx.profile.enabled("GPS.DATUM"):
        return
    text = ctx.pdf.full_text()
    used_positional = [c for c in GDT_POSITIONAL if c in text]
    if not used_positional:
        return
    words = {w.text.strip() for w in ctx.pdf.words()}
    has_datum = any(RE_DATUM.match(w) for w in words if 1 <= len(w) <= 5)
    if not has_datum:
        ctx.add("GPS.DATUM",
                "Lagetoleranzen verwendet, aber kein Bezug (Datum) erkennbar (ISO 1101)",
                detail=f"Gefundene Symbole: {' '.join(used_positional)}")


def check_gdt_contradictions(ctx: CheckContext) -> None:
    """Widersprüchliche bzw. problematische GD&T-Angaben."""
    if ctx.profile.enabled("GPS.FORM_WITH_DATUM"):
        hit = _find(ctx, RE_FORM_WITH_DATUM)
        if hit:
            m, bbox, page = hit
            ctx.add("GPS.FORM_WITH_DATUM",
                    f"Widersprüchliche GD&T: Formtoleranz mit Bezug angegeben "
                    f"(„{m.group(0)}“)",
                    bbox=bbox, page=page,
                    detail="Form (Ebenheit/Geradheit/Rundheit/Zylindrizität) "
                           "ist bezugsunabhängig definiert (ISO 1101) – Bezug "
                           "streichen oder Lage-/Lauftoleranz verwenden.")
    if ctx.profile.enabled("GPS.DEPRECATED_SYMBOL"):
        hit = _find(ctx, RE_DEPRECATED_GDT)
        if hit:
            m, bbox, page = hit
            name = ("Koaxialität/Konzentrizität" if m.group(0) == "◎"
                    else "Symmetrie")
            ctx.add("GPS.DEPRECATED_SYMBOL",
                    f"GD&T-Symbol {m.group(0)} ({name}) verwendet – in "
                    f"ASME Y14.5-2018 gestrichen und messtechnisch problematisch",
                    bbox=bbox, page=page,
                    detail="Für internationale Lieferanten Position bzw. "
                           "Lauf bevorzugen (eindeutig messbar).")


# ------------------------------------------------------ Positionsballone
def check_balloons(ctx: CheckContext) -> None:
    """Stückliste vorhanden, aber keine Positionsballone in der Darstellung.

    Heuristik: Positionsnummern (1, 2, …) müssen als freistehende kurze
    Zahlen AUSSERHALB des Stücklisten-Bereichs auftauchen. Konservativ als
    "Prüfen" gemeldet – Ballon-Grafiken selbst sind nicht auswertbar.
    """
    if not ctx.profile.enabled("DOC.BALLOONS"):
        return
    bom_blocks = [b for b in ctx.pdf.blocks() if RE_BOM_HEADER.search(b.text)]
    if not bom_blocks:
        return
    # Ausschlusszone: x-Spannweite der Stücklisten-Blöcke (Tabellenspalten
    # liegen darüber/darunter in derselben Spur).
    x_ranges = [(b.bbox.x0 - 10, b.bbox.x1 + 10) for b in bom_blocks]
    pages = {b.page for b in bom_blocks}

    def in_bom_column(w) -> bool:
        cx = (w.bbox.x0 + w.bbox.x1) / 2
        return w.page in pages and any(x0 <= cx <= x1 for x0, x1 in x_ranges)

    outside = {w.text.strip() for w in ctx.pdf.words()
               if RE_BALLOON_NUM.match(w.text.strip()) and not in_bom_column(w)}
    missing = [n for n in ("1", "2") if n not in outside]
    if missing:
        b = bom_blocks[0]
        ctx.add("DOC.BALLOONS",
                "Stückliste vorhanden, aber Positionsballone in der "
                "Darstellung nicht erkennbar",
                bbox=b.bbox, page=b.page,
                detail=f"Positionsnummer(n) {', '.join(missing)} wurden "
                       "außerhalb der Stückliste nicht gefunden – ohne Ballone "
                       "ist die Zuordnung Teil ↔ Position nicht eindeutig.")


# ------------------------------------------------------------ Oberflächen
def check_surfaces(ctx: CheckContext) -> None:
    if ctx.profile.enabled("SURF.ROUGHNESS"):
        if (not _find(ctx, RE_ROUGHNESS) and not _find(ctx, RE_SURF_NORM)
                and not _find(ctx, RE_SURF_TEXT)):
            ctx.add("SURF.ROUGHNESS",
                    "Keine Oberflächenangabe nachweisbar (Ra/Rz, ISO 21920/1302 "
                    "oder Freitext)",
                    detail="Mindestens eine Sammelangabe wird erwartet.")
    if (ctx.profile.enabled("SURF.EDGES") and not _find(ctx, RE_ISO13715)
            and not _find(ctx, RE_EDGE_TEXT)):
        ctx.add("SURF.EDGES",
                "Kein Kantenzustand nachweisbar (ISO 13715 oder Freitext "
                "„Kanten gebrochen/entgratet“)",
                detail="Werkstückkanten (Grat/Übergang) sind nicht definiert.")


# ------------------------------------------------------------- Darstellung
def check_view(ctx: CheckContext) -> None:
    if (ctx.profile.enabled("VIEW.PROJECTION") and not _find(ctx, RE_PROJECTION)
            and not _find(ctx, RE_ASME_Y145)):  # ASME => 3. Winkel per Default
        ctx.add("VIEW.PROJECTION",
                "Projektionsmethode nicht nachweisbar (Symbol/Text 1./3. Winkel)",
                detail="Für internationale Lieferanten kritisch (ISO- vs. "
                       "US-Projektion). Symbol ist ggf. nur grafisch vorhanden "
                       "– bitte Sichtprüfung.")
    if ctx.profile.enabled("VIEW.UNIT") and not _find(ctx, RE_UNIT_MM):
        ctx.add("VIEW.UNIT",
                "Einheit nicht deklariert (z. B. „Dimensions in mm“)")


# ------------------------------------------- Kontext: Schweißen und Guss
RE_ISO13920 = re.compile(r"ISO\s*13920", re.IGNORECASE)
# Gewinde fälschlich mit Passungs-Toleranzklasse ("M12 H7" statt 6H/6g).
RE_THREAD_WITH_FIT = re.compile(
    r"\bM\s*\d{1,3}(?:\s*[xX×]\s*\d+(?:[.,]\d+)?)?\s+[HhGgFf]\d{1,2}\b")


def check_thread_fit_class(ctx: CheckContext) -> None:
    if not ctx.profile.enabled("THRD.FIT_CLASS"):
        return
    hit = _find(ctx, RE_THREAD_WITH_FIT)
    if hit:
        m, bbox, page = hit
        ctx.add("THRD.FIT_CLASS",
                f"Gewinde mit Passungs-Toleranzklasse bemaßt („{m.group(0)}“)",
                bbox=bbox, page=page,
                detail="Gewindetoleranzen heißen 6H/6g (ISO 965), "
                       "Bohrungs-/Wellenpassungen H7/h6 gelten nicht für "
                       "Gewinde – Angabe korrigieren.")


def check_welding(ctx: CheckContext) -> None:
    if not ctx.profile.enabled("WELD.QUALITY"):
        return
    hit = _find(ctx, WELD_CONTEXT)
    if not hit:
        return
    # Schweißkonstruktion: ISO 2768 allein reicht nicht – Allgemeintoleranzen
    # für Schweißkonstruktionen sind ISO 13920.
    if (ctx.profile.enabled("NORM.WELD_GENTOL")
            and _find(ctx, RE_ISO2768) and not _find(ctx, RE_ISO13920)):
        ctx.add("NORM.WELD_GENTOL",
                "Schweißkonstruktion nur mit ISO 2768 – Allgemeintoleranzen "
                "für Schweißkonstruktionen (ISO 13920) fehlen",
                detail="ISO 2768 gilt für spanende Fertigung; für Längen-/"
                       "Winkelmaße und Form/Lage geschweißter Baugruppen "
                       "ISO 13920 (z. B. -BF) ergänzen.")
    q = _find(ctx, RE_ISO5817)
    if not q:
        _m, bbox, page = hit
        ctx.add("WELD.QUALITY",
                "Schweißteil ohne Schweißnahtgüte (ISO 5817 Bewertungsgruppe B/C/D)",
                bbox=bbox, page=page,
                detail="Zusätzlich prüfen: Symbolik nach ISO 2553 vollständig?")
    elif q and not q[0].group(1):
        _m, bbox, page = q
        ctx.add("WELD.QUALITY",
                "ISO 5817 ohne Bewertungsgruppe (B/C/D) angegeben",
                bbox=bbox, page=page)


def check_casting(ctx: CheckContext) -> None:
    if not ctx.profile.enabled("CAST.TOL"):
        return
    hit = _find(ctx, CAST_CONTEXT)
    if not hit:
        return
    if not (_find(ctx, RE_ISO8062) or _find(ctx, RE_DCTG) or _find(ctx, RE_CT_GRADE)):
        _m, bbox, page = hit
        ctx.add("CAST.TOL",
                "Gussteil ohne Gusstoleranzangabe (ISO 8062, DCTG/GCTG bzw. CT)",
                bbox=bbox, page=page,
                detail="Auch Bearbeitungszugaben (RMA) prüfen.")


# -------------------------------------------------------------- Konsistenz
def check_consistency(ctx: CheckContext) -> None:
    if not ctx.profile.enabled("CONS.MATNO"):
        return
    material = ctx.material.strip()
    digits = re.sub(r"\D", "", material)
    text = ctx.pdf.full_text()
    found = material and material in text
    if not found and len(digits) >= 6:
        found = digits in re.sub(r"\D", "", text)
    if not found:
        ctx.add("CONS.MATNO",
                f"Materialnummer {material} auf der Zeichnung nicht gefunden",
                detail="Möglicherweise falsches Dokument im YMATDOCS-Paket "
                       "oder Nummer nur in SAP-Metadaten.")


ALL_CHECKS = [
    check_title_block,
    check_general_tolerances,
    check_gps_datums,
    check_gdt_contradictions,
    check_balloons,
    check_thread_fit_class,
    check_surfaces,
    check_view,
    check_welding,
    check_casting,
    check_consistency,
]


def run_drawing_checks(ctx: CheckContext) -> None:
    from .materials import run_material_checks  # später Import: Zyklusfrei

    for check in ALL_CHECKS:
        check(ctx)
    run_material_checks(ctx)
