"""Pruefungen an der Zeichnung selbst: Vollstaendigkeit, Sprache, Massstab.

Titelblock, Schriftfeld, Allgemeintoleranz, Oberflaechenangaben, Sprache
(international beschaffbar?), Massstab gegen die tatsaechliche Geometrie
und die erkannten Fertigungsverfahren.
"""
from __future__ import annotations

# ======================================================================
# drawing_checks
# ======================================================================
# Fachliche Zeichnungs-Checks nach allgemeinen Normen (Sicht: internationaler Einkauf).
#
# Regelgruppen (Codes siehe rules/profiles.yaml):
#   TB.*   Schriftfeld (ISO 7200)
#   GT.*   Allgemeintoleranzen / Tolerierungsgrundsatz (ISO 2768, ISO 22081, ISO 8015)
#   GPS.*  Form- und Lagetolerierung (ISO 1101)
#   SURF.* Oberflächen und Kanten (ISO 21920 / ISO 1302, ISO 13715)
#   VIEW.* Darstellung (Projektionsmethode, Einheit)
#   WELD.* / CAST.*  Kontextregeln für Schweiß- und Gussteile (ISO 2553/5817, ISO 8062)
#   CONS.* Konsistenz zur Anfrage (Materialnummer)
#
# Prinzip: Regeln, die auf der Zeichnung nicht sicher entscheidbar sind, melden
# "nicht nachweisbar" (Severity aus dem Profil, i. d. R. warning) statt hart "fehlt".



import re

from .kern import BBox, Severity
from .regeln import CheckContext

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
# Allgemeintoleranz ohne Normbezug: ASME-Toleranzblock oder Freitext.
# „+/-" ist die ASCII-Schreibweise von ±; ohne sie meldete der Checker an
# 31 echten Zeichnungen des Kalibriersatzes fälschlich „keine
# Allgemeintoleranz" (z. B. „Tolerance unless otherwise noted: +/- 0.25mm").
_PM = r"(?:±|\+/-|\+-)"
RE_ASME_TOLBLOCK = re.compile(
    rf"TOLERANCES?\s*[:\s].{{0,200}}?(?:DECIMAL|{_PM}|ANGULAR)"
    rf"|TOLERANCES?\s+WITHIN\s*{_PM}?\s*\d"     # "TOLERANCES WITHIN 0.1"
    rf"|TOLERANCE[^.\n]{{0,60}}(?:unless|otherwise|noted|specified)"
    rf"[^.\n]{{0,40}}{_PM}?\s*\d"                # "Tolerance unless ...: +/- 0,25"
    rf"|(?:allgemein|frei|unbemaßt)\w*toleranz\w*[^.\n]{{0,40}}{_PM}?\s*\d"
    rf"|(?:alle|all)\s+(?:maße|dimensions)[^.\n]{{0,30}}{_PM}\s*\d"
    rf"|\.X{{1,3}}\s*(?:{_PM}|=)"                 # Toleranzzeilen .X± / .XX±
    rf"|X\.X{{1,3}}\s*(?:{_PM}|=)",
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

# Schweißkontext: NUR eindeutige Belege. Früher stand hier auch ein
# freies "a\d+" für das a-Maß – das traf jede Zeichnungsnummer mit "A01"
# und machte aus 21 gefrästen Teilen des Kalibriersatzes Schweißteile.
# Das a-/z-Maß zählt jetzt nur mit Nahtsymbol (▲/△) davor oder dahinter.
WELD_CONTEXT = re.compile(
    r"schwei[ßs]|\bweld|\bwps\b|\bnaht\b|kehlnaht|stumpfnaht"
    r"|fillet\s*weld|weld\s*seam|ISO\s*2553|ISO\s*5817"
    r"|[▲△]\s*[az]\s?\d|(?<![A-Za-z0-9])[az]\s?\d{1,2}\s*[▲△]",
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
    from .pruef_werkstoff import run_material_checks # später Import: Zyklusfrei

    for check in ALL_CHECKS:
        check(ctx)
    run_material_checks(ctx)


# ======================================================================
# processes
# ======================================================================
# Erkennung der nötigen Fertigungsverfahren aus dem Zeichnungstext.
#
# Für die Prüfdokumentation (Spalte "Fertigungsverfahren" in der Ergebnis-
# Excel). Nutzt dieselben Kontext-Regexe wie die Widerspruchsprüfung, damit
# Dokumentation und Checks nie auseinanderlaufen.



import re

from .zeichnung import DrawingPdf
from .pruef_werkstoff import ( MATERIALS, RE_ANODIZE, RE_BLACKEN, RE_CAST, RE_FIT_TOKEN, RE_HT_CASE, RE_HT_NITR, RE_HT_QT, RE_METRIC_THREAD, RE_STUD_WELD, RE_ZINC, )

RE_PAINT = re.compile(r"lackier|\bRAL\s*\d{4}\b|pulverbeschicht|powder\s*coat"
                      r"|\bKTL\b|paint(?:ed|ing)?\b", re.IGNORECASE)
RE_SHEET = re.compile(r"abgekantet|gekantet|abkanten|biegeradius|kantung"
                      r"|laserzuschnitt|lasergeschnitten|laser\s*cut"
                      r"|sheet\s*metal|\bbend(?:ing|s)?\b|blechdicke",
                      re.IGNORECASE)
RE_GRIND = re.compile(r"geschliffen|schleifen|\bgrinding\b|\bground\b(?!\s*(?:wire|terminal))",
                      re.IGNORECASE)
RE_MACHINING = re.compile(r"machined|spanend|gefräst|gedreht|milling|turning"
                          r"|gebohrt|reiben|geläppt|honen", re.IGNORECASE)

# (Label, Regex) – Reihenfolge = Ausgabereihenfolge in der Excel.
_PROCESS_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Schweißen", WELD_CONTEXT),
    ("Bolzenschweißen", RE_STUD_WELD),
    ("Gießen", RE_CAST),
    ("Blechbearbeitung/Abkanten", RE_SHEET),
    ("Härten/Vergüten", RE_HT_QT),
    ("Einsatzhärten", RE_HT_CASE),
    ("Nitrieren", RE_HT_NITR),
    ("Schleifen", RE_GRIND),
    ("Verzinken", RE_ZINC),
    ("Eloxieren", RE_ANODIZE),
    ("Brünieren", RE_BLACKEN),
    ("Lackieren/Beschichten", RE_PAINT),
    ("Gewindefertigung", RE_METRIC_THREAD),
]


def detect_processes(pdf: DrawingPdf) -> list[str]:
    text = pdf.full_text()
    if not text.strip():
        return []
    found = [label for label, regex in _PROCESS_PATTERNS if regex.search(text)]

    # Spanende Bearbeitung: explizit genannt ODER über Oberflächen-/
    # Passungsangaben impliziert.
    if (RE_MACHINING.search(text) or RE_ROUGHNESS.search(text)
            or RE_FIT_TOKEN.search(text)):
        found.append("Spanende Bearbeitung")

    # Gusswerkstoff erkannt, aber kein expliziter Guss-Kontext im Text.
    if "Gießen" not in found:
        for mat in MATERIALS:
            if mat.castable and any(
                    re.search(p, text, re.IGNORECASE) for p in mat.patterns):
                found.insert(0, "Gießen")
                break
    return found


# ======================================================================
# language_check
# ======================================================================
# Sprach-Check: rein deutschsprachige Beschriftungen sind ein Finding.
#
# Hintergrund: Die Zeichnungen gehen an internationale Lieferanten – deutsche
# Anmerkungen sind dort nicht lesbar. Zweisprachige Beschriftung ist ok.
#
# Umsetzung ohne externe Modelle: Stoppwort-/Lexikon-Scoring je Textblock.
# Deterministisch, offline, und die Wortlisten sind auf technische
# Zeichnungssprache zugeschnitten.



import re

from .regeln import CheckContext

# Häufige deutsche Funktions- und Zeichnungswörter.
GERMAN_WORDS = {
    "und", "oder", "mit", "ohne", "nach", "vor", "bei", "der", "die", "das",
    "den", "dem", "des", "ein", "eine", "einer", "nicht", "alle", "sind",
    "ist", "wird", "werden", "muss", "müssen", "darf", "dürfen", "siehe",
    "für", "auf", "aus", "über", "unter", "zwischen", "sowie", "bzw",
    "kanten", "kante", "gebrochen", "entgratet", "entgraten", "gratfrei",
    "scharfkantig", "maße", "masse", "maß", "allgemeintoleranzen",
    "allgemeintoleranz", "werkstoff", "oberfläche", "oberflächen", "gewicht",
    "maßstab", "blatt", "änderung", "änderungen", "zeichnung", "benennung",
    "datum", "geprüft", "erstellt", "freigabe", "freigegeben", "bemerkung",
    "anmerkung", "hinweis", "ausführung", "beschichtung", "verzinkt",
    "lackiert", "geglüht", "gehärtet", "vergütet", "geschweißt", "schweißen",
    "schweißnaht", "schweißnähte", "nahtdicke", "ringsum", "umlaufend",
    "beidseitig", "allseitig", "gussteil", "rohteil", "fertigteil", "zugabe",
    "bearbeitungszugabe", "wärmebehandlung", "prüfung", "kennzeichnung",
    "teilenummer", "stückzahl", "halbzeug", "unbemaßt", "gelten", "gilt",
    "angaben", "toleranzen", "toleranz", "passung", "gewinde", "bohrung",
    "bohrungen", "senkung", "fase", "fasen", "radien", "innenliegend",
}
# Häufige englische Funktions- und Zeichnungswörter.
ENGLISH_WORDS = {
    "and", "or", "with", "without", "the", "all", "are", "is", "shall",
    "must", "may", "see", "for", "from", "not", "of", "to", "in", "on",
    "edges", "edge", "broken", "deburred", "burr", "free", "sharp",
    "dimensions", "dimension", "general", "tolerances", "tolerance",
    "material", "surface", "surfaces", "weight", "scale", "sheet",
    "revision", "drawing", "title", "date", "checked", "drawn", "approved",
    "released", "note", "notes", "remark", "finish", "coating", "galvanized",
    "painted", "hardened", "annealed", "welded", "welding", "weld", "seam",
    "around", "both", "sides", "casting", "cast", "raw", "machining",
    "allowance", "heat", "treatment", "unless", "otherwise", "specified",
    "apply", "applies", "marking", "part", "quantity", "thread", "hole",
    "holes", "chamfer", "radii", "internal", "number",
    "pressure", "test", "tolerancing", "per", "datum", "datums", "base",
    "face", "faces", "bearing", "bore", "bores", "key", "keyway", "seat",
    "seats", "detail", "centre", "center", "end", "ends", "machined",
    "paint", "quenched", "tempered", "hardness", "grade", "quality",
}
UMLAUT = re.compile(r"[äöüßÄÖÜ]")
WORD = re.compile(r"[A-Za-zÄÖÜäöüß]{2,}")
# Tokens, die nie Sprachindiz sind (Normbezüge, Kürzel).
NEUTRAL = {"iso", "din", "en", "ra", "rz", "mm", "kg", "max", "min", "typ",
           "nr", "no", "pos", "st", "ca", "ø", "vgl", "asme", "gjs", "gjl"}


def classify_block(text: str) -> str:
    """'de' | 'en' | 'mixed' | 'neutral' für einen Textblock.

    'mixed' = Block enthält deutsche UND englische Signale (zweisprachige
    Beschriftung) – das ist für den internationalen Einkauf in Ordnung.
    """
    words = [w.lower() for w in WORD.findall(text)]
    words = [w for w in words if w not in NEUTRAL]
    if not words:
        return "neutral"
    de = sum(1 for w in words if w in GERMAN_WORDS)
    en = sum(1 for w in words if w in ENGLISH_WORDS)
    de += 2 * len(UMLAUT.findall(text))  # Umlaute sind ein starkes Signal
    if de and en:
        return "mixed"
    if de:
        return "de"
    if en:
        return "en"
    return "neutral"


def check_language(ctx: CheckContext) -> None:
    """Markiert deutsche Textblöcke ohne englische Entsprechung."""
    if not ctx.profile.enabled("LANG.GERMAN"):
        return
    german_blocks = []
    has_english = False
    for block in ctx.pdf.blocks():
        cls = classify_block(block.text)
        if cls == "de":
            german_blocks.append(block)
        elif cls in ("en", "mixed"):
            has_english = True

    if not german_blocks:
        return

    max_markers = int(ctx.profile.params.get("max_language_markers", 12))
    note = (" (Zeichnung enthält auch englischen Text – prüfen, ob durchgehend "
            "zweisprachig)" if has_english else "")
    for block in german_blocks[:max_markers]:
        snippet = block.text.replace("\n", " ")
        if len(snippet) > 60:
            snippet = snippet[:57] + "…"
        ctx.add(
            "LANG.GERMAN",
            f"Deutschsprachige Beschriftung: „{snippet}“",
            bbox=block.bbox, page=block.page,
            detail="Für internationalen Einkauf englisch oder zweisprachig "
                   "beschriften." + note,
        )
    rest = len(german_blocks) - max_markers
    if rest > 0:
        ctx.add(
            "LANG.GERMAN",
            f"… und {rest} weitere deutschsprachige Textstellen",
            detail="Nur die ersten Fundstellen sind im Bild markiert.",
        )


# ======================================================================
# doc_checks
# ======================================================================
# Dokumenten-Formalien: Vollständigkeit und Beherrschbarkeit der Datei.
#
# Fehler, die nichts mit der Konstruktion zu tun haben, aber im Einkauf
# regelmäßig zu Rückfragen, Nachträgen oder falsch gefertigten Teilen führen:
#
#   DOC.SHEET_COUNT  „Blatt 1 von 3", geliefert wird 1 Seite – die Zeichnung
#                    ist unvollständig; die fehlenden Blätter enthalten oft
#                    genau die Toleranz- und Schweißangaben.
#   DOC.ANNOTATIONS  Das PDF enthält nachträgliche Kommentare, Stempel oder
#                    Freihandmarkierungen. Solche Rotstiftänderungen sind
#                    nicht Teil des freigegebenen Standes.
#   DOC.DATE_FUTURE  Datum auf der Zeichnung liegt in der Zukunft oder
#                    unplausibel weit zurück – Hinweis auf Tippfehler im
#                    Änderungsstand.
#   DOC.DECIMAL_MIXED Dezimalkomma und Dezimalpunkt gemischt. Für einen
#                    internationalen Lieferanten ein echtes Risiko
#                    („1.500" = 1,5 oder 1500?).



import datetime as _dt
import logging
import re

from .kern import BBox
from .regeln import CheckContext

log = logging.getLogger(__name__)

# „Blatt 1 von 3", „Blatt 1/3", „Sheet 2 of 4", „Bl. 1 v. 2"
RE_SHEET_OF = re.compile(
    r"\b(?:blatt|bl\.?|sheet|feuille|page)\s*(\d{1,2})\s*"
    r"(?:von|v\.|of|/)\s*(\d{1,2})\b", re.IGNORECASE)
# Anmerkungstypen, die eine echte Nachbearbeitung darstellen.
MARKUP_ANNOTS = {
    "Text", "FreeText", "Ink", "Square", "Circle", "Line", "Polygon",
    "PolyLine", "Highlight", "Underline", "Squiggly", "StrikeOut", "Stamp",
    "Caret", "FileAttachment",
}
# Zahlen mit Dezimaltrenner (ohne Normbezeichnungen wie „ISO 2768-1").
RE_DEC_COMMA = re.compile(r"(?<![\d.,])\d{1,4},\d{1,3}(?![\d.,])")
RE_DEC_POINT = re.compile(r"(?<![\d.,])\d{1,4}\.\d{1,3}(?![\d.,])")


def run_doc_checks(ctx: CheckContext) -> None:
    check_sheet_count(ctx)
    check_annotations(ctx)
    check_dates(ctx)
    check_decimal_separator(ctx)


def check_sheet_count(ctx: CheckContext) -> None:
    """Angekündigte Blattzahl gegen die tatsächlichen PDF-Seiten prüfen."""
    if not ctx.profile.enabled("DOC.SHEET_COUNT"):
        return
    declared = 0
    for block in ctx.pdf.blocks():
        for _no, total in RE_SHEET_OF.findall(block.text):
            declared = max(declared, int(total))
    if declared <= 1:
        return
    actual = ctx.pdf.page_count
    if actual >= declared:
        return
    ctx.add("DOC.SHEET_COUNT",
            f"Zeichnung ist unvollständig: angekündigt sind {declared} "
            f"Blätter, das Paket enthält {actual}",
            detail="Fehlende Folgeblätter enthalten erfahrungsgemäß "
                   "Schweiß-, Toleranz- und Prüfangaben. Vollständiges "
                   "Dokument anfordern, bevor angefragt wird.")


def check_annotations(ctx: CheckContext) -> None:
    """Nachträgliche PDF-Markierungen (Rotstift) erkennen."""
    if not ctx.profile.enabled("DOC.ANNOTATIONS"):
        return
    found: list[tuple[str, int, BBox | None]] = []
    try:
        for pno, page in enumerate(ctx.pdf.doc):
            for annot in page.annots() or []:
                kind = (annot.type[1] if isinstance(annot.type, (list, tuple))
                        else str(annot.type))
                if kind not in MARKUP_ANNOTS:
                    continue
                r = annot.rect
                found.append((kind, pno, BBox(r.x0, r.y0, r.x1, r.y1)))
    except Exception:      # pragma: no cover - defekte/exotische PDFs
        log.debug("Annotationen nicht lesbar", exc_info=True)
        return
    if not found:
        return
    kinds = ", ".join(sorted({k for k, _p, _b in found}))
    kind, page, bbox = found[0]
    ctx.add("DOC.ANNOTATIONS",
            f"{len(found)} nachträgliche Markierung(en) im PDF ({kinds})",
            bbox=bbox, page=page,
            detail="Kommentare, Stempel oder Freihandeinträge gehören nicht "
                   "zum freigegebenen Stand. Entweder in die Zeichnung "
                   "einarbeiten und den Index hochsetzen oder entfernen – "
                   "ein Lieferant sieht sie je nach Betrachter gar nicht.")


def check_dates(ctx: CheckContext) -> None:
    """Datumsangaben auf Plausibilität prüfen."""
    if not ctx.profile.enabled("DOC.DATE_FUTURE"):
        return
    from .zeichnung import _candidates # gemeinsame Datumslogik

    today = _dt.date.today()
    dates = [d for d in _candidates(ctx.pdf.full_text())]
    if not dates:
        return
    newest = max(dates)
    if newest > today:
        ctx.add("DOC.DATE_FUTURE",
                f"Datum auf der Zeichnung liegt in der Zukunft: "
                f"{newest.isoformat()}",
                detail="Meist ein Tippfehler im Änderungsdatum. Für die "
                       "Dokumentation des Prüflaufs wird das Datum trotzdem "
                       "übernommen.")


def check_decimal_separator(ctx: CheckContext) -> None:
    """Gemischte Dezimaltrenner erkennen (international missverständlich)."""
    if not ctx.profile.enabled("DOC.DECIMAL_MIXED"):
        return
    text = ctx.pdf.full_text()
    commas = len(RE_DEC_COMMA.findall(text))
    points = len(RE_DEC_POINT.findall(text))
    minimum = int(ctx.profile.rule_param("DOC.DECIMAL_MIXED", "min_count", 3))
    if commas < minimum or points < minimum:
        return
    ctx.add("DOC.DECIMAL_MIXED",
            f"Dezimaltrenner gemischt: {commas}× Komma, {points}× Punkt",
            detail="Aus Sicht eines internationalen Lieferanten mehrdeutig – "
                   "„1.500\" kann 1,5 oder 1500 bedeuten. Durchgängig einen "
                   "Trenner verwenden (ISO 80000-1 empfiehlt das Komma, "
                   "verbreitet ist im Export der Punkt).")


# ======================================================================
# scale_checks
# ======================================================================
# Maßstabsbasierte Prüfungen: gemessene Ansicht statt Maßtext.
#
# Aus Schriftfeld-Maßstab und der gemessenen Größe der Zeichnungsansicht
# ergibt sich die Bauteilgröße – völlig unabhängig von der Maßtext-Extraktion.
# Das liefert zwei Prüfungen:
#
#   SCALE.MISMATCH   Gemessene Ansicht passt nicht zu den eingetragenen Maßen:
#                    entweder ist die Zeichnung nicht maßstäblich oder der
#                    Maßstab im Schriftfeld ist falsch.
#   GEO.VIEW_SIZE    Gemessene Ansicht passt nicht zum STEP-Modell. Greift
#                    auch dann, wenn die Maßextraktion nichts hergibt
#                    (schlechter Textlayer, OCR).
#
# Beide sind bewusst großzügig toleriert: Detail- und Schnittansichten mit
# abweichendem Maßstab, Bemaßungsüberstände und gerundete Maßstabsangaben
# dürfen nicht zu Fehlalarmen führen.



import logging

from .zeichnung import DimKind, DimValue
from .zeichnung import extract_scale, mm_per_point
from .regeln import CheckContext



def measure_largest_view(ctx: CheckContext, scale: float
                         ) -> tuple[float, float, object] | None:
    """Größte Zeichnungsansicht in Bauteil-Millimetern.

    Rückgabe: (Breite, Höhe, Ansicht) oder None.
    """
    from .pruef_geometrie import extract_views

    try:
        views = extract_views(ctx.pdf)
    except Exception:  # Stub-PDFs in Tests
        return None
    if not views:
        return None
    factor = mm_per_point(scale)
    best = None
    for v in views:
        x0, y0, x1, y1 = v.bbox
        w, h = (x1 - x0) * factor, (y1 - y0) * factor
        if best is None or w * h > best[0] * best[1]:
            best = (w, h, v)
    return best


def check_scale_consistency(ctx: CheckContext, dims: list[DimValue]) -> str:
    """Gemessene Ansichtsgröße gegen die eingetragenen Maße prüfen.

    Rückgabe: Kurztext für die Excel-Vergleichswerte.
    """
    scale = extract_scale(ctx.pdf)
    if scale is None:
        return ""
    measured = measure_largest_view(ctx, scale)
    if measured is None:
        return ""
    width, height, view = measured
    largest_view = max(width, height)
    if largest_view < 1:
        return ""

    values = [d.value for d in dims
              if d.kind in (DimKind.LINEAR, DimKind.DIAMETER)]
    summary = (f"Ansicht gemessen {width:.0f} × {height:.0f} mm "
               f"(Maßstab 1:{scale:g})")
    if not values:
        return summary
    if not ctx.profile.enabled("SCALE.MISMATCH"):
        return summary        # nur messen, nicht bewerten
    largest_dim = max(values)
    tol = float(ctx.profile.params.get("scale_tol", 0.15))
    # Bewusst einseitig: Eine Ansicht kann durch unvollständig erkannte
    # Konturlinien zu KLEIN gemessen werden – das ist kein Zeichnungsfehler.
    # Nur eine Ansicht, die GRÖSSER ist als das größte eingetragene Maß,
    # ist ein sicheres Zeichen für einen falschen Maßstab.
    deviation = (largest_view - largest_dim) / max(largest_dim, 1)
    if deviation > tol:
        ctx.add("SCALE.MISMATCH",
                f"Zeichnung nicht maßstäblich: gemessene Ansicht "
                f"{largest_view:.0f} mm überschreitet das größte eingetragene "
                f"Maß ({largest_dim:g} mm) bei Maßstab 1:{scale:g}",
                bbox=_view_bbox(view), page=0,
                detail="Entweder stimmt der Maßstab im Schriftfeld nicht, "
                       "oder die Ansicht wurde nachträglich verzerrt/skaliert. "
                       "Für den Lieferanten ist die Zeichnung dann nur noch "
                       "über die Maßzahlen nutzbar.")
    return summary


def check_view_vs_model(ctx: CheckContext, geometry, dims: list[DimValue]
                        ) -> None:
    """Gemessene Ansichtsgröße gegen die Modell-Bounding-Box prüfen.

    Unabhängig von den Maßtexten – deshalb auch bei schwachem Textlayer
    aussagekräftig.
    """
    if not ctx.profile.enabled("GEO.VIEW_SIZE") or geometry.backend != "occ":
        return
    scale = extract_scale(ctx.pdf)
    if scale is None:
        return
    measured = measure_largest_view(ctx, scale)
    if measured is None:
        return
    width, height, view = measured
    largest_view = max(width, height)
    obb_max = geometry.obb_dims[0]
    if largest_view < 1 or obb_max <= 0:
        return
    tol = float(ctx.profile.params.get("view_model_tol", 0.2))
    # Ebenfalls einseitig (s. check_scale_consistency): zu klein gemessene
    # Ansichten sind ein Erkennungs-, kein Zeichnungsproblem.
    deviation = (largest_view - obb_max) / obb_max
    if deviation <= tol:
        return
    # Bei bereits erkanntem Einheiten- oder Maßstabsfehler nicht doppelt melden.
    known = {f.code for f in ctx.findings}
    if {"GEO.UNIT_MISMATCH", "SCALE.MISMATCH"} & known:
        return
    ctx.add("GEO.VIEW_SIZE",
            f"Gemessene Ansicht ({largest_view:.0f} mm) ist größer als das "
            f"Modell ({obb_max:.0f} mm)",
            bbox=_view_bbox(view), page=0,
            detail=f"Abweichung {deviation * 100:.0f} % bei Maßstab "
                   f"1:{scale:g}. Unabhängig von den Maßzahlen gemessen – "
                   f"stützt den Verdacht auf ein falsch zugeordnetes Modell.")


def _view_bbox(view):
    from .kern import BBox

    x0, y0, x1, y1 = view.bbox
    return BBox(x0, y0, x1, y1)
