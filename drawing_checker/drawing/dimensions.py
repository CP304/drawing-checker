"""Extraktion von Maßangaben aus dem Zeichnungs-PDF.

Grundlage für den Geometrieabgleich gegen STEP: aus den Maßtexten der
Zeichnung werden die plausiblen Hüllmaße geschätzt. Die Extraktion ist
bewusst konservativ – lieber ein Maß übersehen als eine Normbezeichnung
("ISO 2768") als 2768-mm-Maß fehlinterpretieren.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from ..core.models import BBox
from .pdfdoc import DrawingPdf, Word


class DimKind(Enum):
    LINEAR = "linear"
    DIAMETER = "diameter"
    RADIUS = "radius"
    THREAD = "thread"


@dataclass
class DimValue:
    value: float          # Nennmaß in mm
    kind: DimKind
    raw: str              # Originaltext
    bbox: BBox
    page: int


# Zahl mit deutschem oder englischem Dezimaltrenner.
NUM = r"(\d{1,4}(?:[.,]\d{1,3})?)"
# Optionale Toleranzanhängsel: ±0,1 | +0,2 | -0,1 | H7 | h6 | js9 ...
TOL = r"(?:\s*(?:±\s*\d+(?:[.,]\d+)?|[+-]\s*\d+(?:[.,]\d+)?|[A-Za-z]{1,2}\d{1,2}))?"

RE_DIAMETER = re.compile(rf"[⌀Øø∅]\s*{NUM}{TOL}")
RE_RADIUS = re.compile(rf"\bR\s*{NUM}\b")
RE_THREAD = re.compile(rf"\bM\s*{NUM}(?:\s*[xX×]\s*\d+(?:[.,]\d+)?)?\b")
RE_LINEAR = re.compile(rf"^{NUM}{TOL}$")
RE_FIT = re.compile(rf"^{NUM}\s*[A-Za-z]{{1,2}}\d{{1,2}}$")  # z. B. 40H7
RE_TOLERANCED = re.compile(rf"^{NUM}\s*±")

# Kontexte, in denen Zahlen KEINE Maße sind.
NORM_WORDS = {"iso", "din", "en", "vdi", "asme", "ansi", "nf", "bs", "sep", "vdg"}
UNIT_NOT_MM = re.compile(r"(kg|g|°|grad|deg|%|:|/)", re.IGNORECASE)
RE_SCALE = re.compile(r"^\d+\s*:\s*\d+$")
RE_LONG_ID = re.compile(r"^\d{6,}$")  # Zeichnungs-/Materialnummern
RE_YEAR = re.compile(r"^(19|20)\d{2}$")


def parse_number(s: str) -> float:
    return float(s.replace(",", "."))


def extract_dimensions(pdf: DrawingPdf, max_plausible: float = 6000.0) -> list[DimValue]:
    """Extrahiert alle Maßkandidaten aus den Wörtern des PDFs."""
    words = pdf.words()
    dims: list[DimValue] = []
    for i, w in enumerate(words):
        prev = words[i - 1].text.lower().rstrip(".:") if i > 0 else ""
        for d in _parse_word(w, prev_word=prev):
            if 0.1 <= d.value <= max_plausible:
                dims.append(d)
    return dims


def _parse_word(w: Word, prev_word: str) -> list[DimValue]:
    t = w.text.strip()
    out: list[DimValue] = []

    for m in RE_DIAMETER.finditer(t):
        out.append(DimValue(parse_number(m.group(1)), DimKind.DIAMETER, t, w.bbox, w.page))
    for m in RE_THREAD.finditer(t):
        out.append(DimValue(parse_number(m.group(1)), DimKind.THREAD, t, w.bbox, w.page))
    if out:
        return out
    m = RE_RADIUS.search(t)
    if m:
        return [DimValue(parse_number(m.group(1)), DimKind.RADIUS, t, w.bbox, w.page)]

    # Lineare Maße nur, wenn das ganze Token wie ein Maß aussieht und der
    # Kontext nicht dagegen spricht (Normbezug, Maßstab, ID-Nummer, Jahr).
    if prev_word in NORM_WORDS:
        return []
    if UNIT_NOT_MM.search(t) or RE_SCALE.match(t) or RE_LONG_ID.match(t) or RE_YEAR.match(t):
        return []
    for regex in (RE_TOLERANCED, RE_FIT, RE_LINEAR):
        m = regex.match(t)
        if m:
            return [DimValue(parse_number(m.group(1)), DimKind.LINEAR, t, w.bbox, w.page)]
    return []


def estimate_envelope(dims: list[DimValue], top_n: int = 6) -> list[float]:
    """Schätzt die Hüllmaß-Kandidaten der Zeichnung.

    Liefert die größten `top_n` voneinander verschiedenen Werte aus linearen
    Maßen und Durchmessern, absteigend sortiert. Die größten konsistenten
    Maße dominieren erfahrungsgemäß die Außenkontur.
    """
    candidates = sorted(
        {round(d.value, 2) for d in dims if d.kind in (DimKind.LINEAR, DimKind.DIAMETER)},
        reverse=True,
    )
    return candidates[:top_n]
