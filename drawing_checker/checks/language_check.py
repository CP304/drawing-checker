"""Sprach-Check: rein deutschsprachige Beschriftungen sind ein Finding.

Hintergrund: Die Zeichnungen gehen an internationale Lieferanten – deutsche
Anmerkungen sind dort nicht lesbar. Zweisprachige Beschriftung ist ok.

Umsetzung ohne externe Modelle: Stoppwort-/Lexikon-Scoring je Textblock.
Deterministisch, offline, und die Wortlisten sind auf technische
Zeichnungssprache zugeschnitten.
"""
from __future__ import annotations

import re

from .base import CheckContext

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
