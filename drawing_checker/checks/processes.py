"""Erkennung der nötigen Fertigungsverfahren aus dem Zeichnungstext.

Für die Prüfdokumentation (Spalte "Fertigungsverfahren" in der Ergebnis-
Excel). Nutzt dieselben Kontext-Regexe wie die Widerspruchsprüfung, damit
Dokumentation und Checks nie auseinanderlaufen.
"""
from __future__ import annotations

import re

from ..drawing.pdfdoc import DrawingPdf
from .drawing_checks import RE_ROUGHNESS, WELD_CONTEXT
from .materials import (
    MATERIALS, RE_ANODIZE, RE_BLACKEN, RE_CAST, RE_FIT_TOKEN, RE_HT_CASE,
    RE_HT_NITR, RE_HT_QT, RE_METRIC_THREAD, RE_STUD_WELD, RE_ZINC,
)

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
