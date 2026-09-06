"""Extraktion von Maßangaben aus dem Zeichnungs-PDF.

Grundlage für den Geometrieabgleich gegen STEP und für die Bemaßungs-/
Fertigungsregeln. Die Extraktion ist bewusst konservativ – lieber ein Maß
übersehen als eine Normbezeichnung ("ISO 2768") als 2768-mm-Maß
fehlinterpretieren.

Erfasst je Maß:
  * Nennwert und Art (linear, Durchmesser, Radius, Gewinde)
  * Wiederholfaktor ("4×⌀18" -> count=4)
  * Toleranz (±0,1 -> tol_plus/tol_minus; Grenzabmaße +0,2/-0,1)
  * ISO-Passung ("40H7" -> fit="H7") inkl. IT-Grad
  * theoretisch genaues Maß (eingerahmt, ISO 1101) -> is_basic
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
    value: float                 # Nennmaß in mm
    kind: DimKind
    raw: str                     # Originaltext
    bbox: BBox
    page: int
    count: int = 1               # Wiederholfaktor ("4×⌀18")
    tol_plus: float | None = None
    tol_minus: float | None = None
    fit: str = ""                # ISO-Passung, z. B. "H7"
    is_basic: bool = False       # theoretisch genaues Maß (eingerahmt)
    depth: float | None = None   # Bohrtiefe ("⌀8 ↧25" / "⌀8 T25")

    @property
    def tolerance_span(self) -> float | None:
        """Toleranzbreite in mm (aus ± bzw. Grenzabmaßen oder ISO-Passung)."""
        if self.tol_plus is not None or self.tol_minus is not None:
            hi = self.tol_plus if self.tol_plus is not None else 0.0
            lo = self.tol_minus if self.tol_minus is not None else 0.0
            return abs(hi - lo)
        if self.fit:
            return it_grade_span(self.fit, self.value)
        return None

    @property
    def it_grade(self) -> int | None:
        m = re.search(r"(\d{1,2})$", self.fit)
        return int(m.group(1)) if m else None


# --------------------------------------------------------------------------
# ISO-286 Grundtoleranzgrade (Auszug): Toleranzbreite in µm je Nennmaßbereich.
# Reicht für die Bewertung "wie eng ist diese Toleranz" völlig aus.
# --------------------------------------------------------------------------
_IT_RANGES = [3, 6, 10, 18, 30, 50, 80, 120, 180, 250, 315, 400, 500]
_IT_TABLE_UM = {
    #    ≤3   ≤6  ≤10  ≤18  ≤30  ≤50  ≤80 ≤120 ≤180 ≤250 ≤315 ≤400 ≤500
    1: [0.8, 1, 1, 1.2, 1.5, 1.5, 2, 2.5, 3.5, 4.5, 6, 7, 8],
    2: [1.2, 1.5, 1.5, 2, 2.5, 2.5, 3, 4, 5, 7, 8, 9, 10],
    3: [2, 2.5, 2.5, 3, 4, 4, 5, 6, 8, 10, 12, 13, 15],
    4: [3, 4, 4, 5, 6, 7, 8, 10, 12, 14, 16, 18, 20],
    5: [4, 5, 6, 8, 9, 11, 13, 15, 18, 20, 23, 25, 27],
    6: [6, 8, 9, 11, 13, 16, 19, 22, 25, 29, 32, 36, 40],
    7: [10, 12, 15, 18, 21, 25, 30, 35, 40, 46, 52, 57, 63],
    8: [14, 18, 22, 27, 33, 39, 46, 54, 63, 72, 81, 89, 97],
    9: [25, 30, 36, 43, 52, 62, 74, 87, 100, 115, 130, 140, 155],
    10: [40, 48, 58, 70, 84, 100, 120, 140, 160, 185, 210, 230, 250],
    11: [60, 75, 90, 110, 130, 160, 190, 220, 250, 290, 320, 360, 400],
    12: [100, 120, 150, 180, 210, 250, 300, 350, 400, 460, 520, 570, 630],
    13: [140, 180, 220, 270, 330, 390, 460, 540, 630, 720, 810, 890, 970],
}


def it_grade_span(fit: str, nominal: float) -> float | None:
    """Toleranzbreite einer ISO-Passung in mm (None wenn unbekannt)."""
    m = re.search(r"(\d{1,2})$", fit or "")
    if not m:
        return None
    grade = int(m.group(1))
    row = _IT_TABLE_UM.get(grade)
    if row is None or nominal <= 0:
        return None
    idx = next((i for i, upper in enumerate(_IT_RANGES) if nominal <= upper),
               len(_IT_RANGES) - 1)
    return row[min(idx, len(row) - 1)] / 1000.0


# --------------------------------------------------------------------------
# Regex-Bausteine
# --------------------------------------------------------------------------
NUM = r"(\d{1,4}(?:[.,]\d{1,3})?)"
DIA = r"[⌀Øø∅]"
# Wiederholfaktor: "4x", "4×", "4 X"
MULT = r"(?:(\d{1,3})\s*[xX×]\s*)?"
# ISO-Passung: gültige Toleranzlagen nach ISO 286 (einbuchstabig oder
# die zweibuchstabigen Sonderlagen), z. B. H7, h6, js9, JS13, k6.
FIT_LETTERS = r"(?:JS|js|CD|cd|EF|ef|FG|fg|Z[ABC]|z[abc]|[A-Za-z])"
FIT = rf"(?:\s*({FIT_LETTERS}\d{{1,2}}))?"
# Symmetrische Toleranz: ±0,1
TOL_SYM = r"(?:\s*±\s*(\d+(?:[.,]\d+)?))?"
# Grenzabmaße: +0,2 -0,1  (auch mit Leerzeichen/Zeilenumbruch dazwischen)
TOL_LIM = r"(?:\s*\+\s*(\d+(?:[.,]\d+)?)\s*[-−]\s*(\d+(?:[.,]\d+)?))?"

RE_DIAMETER = re.compile(rf"{MULT}{DIA}\s*{NUM}{FIT}{TOL_SYM}")
RE_RADIUS = re.compile(rf"\bR\s*{NUM}\b")
RE_THREAD = re.compile(
    rf"(?:(\d{{1,3}})\s*[xX×]\s*M|\bM)\s*{NUM}"
    rf"(?:\s*[xX×]\s*(\d+(?:[.,]\d+)?))?\b")
RE_LINEAR = re.compile(rf"^{NUM}{FIT}{TOL_SYM}$")
RE_LIMITS = re.compile(rf"^{NUM}\s*\+\s*(\d+(?:[.,]\d+)?)\s*[-−]\s*"
                       rf"(\d+(?:[.,]\d+)?)$")
# Theoretisch genaues Maß (TED): eingerahmt, im Textlayer meist als
# "[50]" oder mit Rahmen-Unicode. Wir erkennen die Klammerformen.
RE_BASIC = re.compile(rf"^[\[⟦(]\s*{NUM}\s*[\]⟧)]$")
# Allein stehende Passung ("H7") bzw. Toleranz ("±0,1") als Folgewort.
RE_FIT_ONLY = re.compile(rf"^({FIT_LETTERS}\d{{1,2}})$")
RE_TOL_ONLY = re.compile(r"^±\s*(\d+(?:[.,]\d+)?)$")
# Bohrtiefe: "↧25", "T25", "tief 25"
RE_DEPTH = re.compile(r"(?:↧|\bT(?=\d)|\btief\s*|\bdeep\s*)\s*(\d{1,4}"
                      r"(?:[.,]\d{1,2})?)", re.IGNORECASE)

# Kontexte, in denen Zahlen KEINE Maße sind.
NORM_WORDS = {"iso", "din", "en", "vdi", "asme", "ansi", "nf", "bs", "sep",
              "vdg", "awt", "aws", "sae", "astm", "ral"}
UNIT_NOT_MM = re.compile(r"(kg|g\b|°|grad|deg|%|:|/|µm|hrc|hv|hb)",
                         re.IGNORECASE)
RE_SCALE = re.compile(r"^\d+\s*:\s*\d+$")
RE_LONG_ID = re.compile(r"^\d{6,}$")
RE_YEAR = re.compile(r"^(19|20)\d{2}$")


def parse_number(s: str) -> float:
    return float(s.replace(",", "."))


def _num_or_none(s) -> float | None:
    return parse_number(s) if s else None


def extract_dimensions(pdf: DrawingPdf, max_plausible: float = 6000.0
                       ) -> list[DimValue]:
    """Extrahiert alle Maßkandidaten aus den Wörtern des PDFs."""
    words = pdf.words()
    dims: list[DimValue] = []
    for i, w in enumerate(words):
        prev = words[i - 1].text.lower().rstrip(".:") if i > 0 else ""
        # Nachbarwörter für Kontextangaben (Tiefe, Grenzabmaße, Faktor)
        nxt = " ".join(x.text for x in words[i + 1:i + 3])
        for d in _parse_word(w, prev_word=prev, next_text=nxt):
            if 0.05 <= d.value <= max_plausible:
                dims.append(d)
    return dims


def _parse_word(w: Word, prev_word: str, next_text: str = "") -> list[DimValue]:
    t = w.text.strip()
    out: list[DimValue] = []

    def mk(value, kind, **kw) -> DimValue:
        d = DimValue(value=value, kind=kind, raw=t, bbox=w.bbox, page=w.page,
                     **kw)
        # Tiefe steht oft im Folgewort ("⌀8", "↧25")
        dm = RE_DEPTH.search(next_text)
        if dm and kind in (DimKind.DIAMETER, DimKind.THREAD):
            d.depth = parse_number(dm.group(1))
        # Passung und Toleranz stehen häufig als eigenes Token dahinter
        # ("⌀20" "H7" bzw. "40" "±0,1") – CAD-Systeme trennen sie oft.
        if kind in (DimKind.DIAMETER, DimKind.LINEAR):
            head = next_text.split()[:1]
            if head and not d.fit:
                fm = RE_FIT_ONLY.match(head[0])
                if fm:
                    d.fit = fm.group(1)
                    d.raw = f"{t} {head[0]}"
            if head and d.tol_plus is None:
                tm = RE_TOL_ONLY.match(head[0])
                if tm:
                    v = parse_number(tm.group(1))
                    d.tol_plus, d.tol_minus = v, -v
                    d.raw = f"{t} {head[0]}"
        return d

    # --- Durchmesser (inkl. Anzahl und Passung) ---------------------------
    for m in RE_DIAMETER.finditer(t):
        count, value, fit, tol = m.group(1), m.group(2), m.group(3), m.group(4)
        tol_v = _num_or_none(tol)
        out.append(mk(parse_number(value), DimKind.DIAMETER,
                      count=int(count) if count else 1,
                      fit=fit or "",
                      tol_plus=tol_v, tol_minus=-tol_v if tol_v else None))
    # --- Gewinde ----------------------------------------------------------
    for m in RE_THREAD.finditer(t):
        count, value = m.group(1), m.group(2)
        out.append(mk(parse_number(value), DimKind.THREAD,
                      count=int(count) if count else 1))
    if out:
        return out

    m = RE_RADIUS.search(t)
    if m:
        return [mk(parse_number(m.group(1)), DimKind.RADIUS)]

    # --- Lineare Maße: nur wenn das ganze Token wie ein Maß aussieht ------
    if prev_word in NORM_WORDS:
        return []
    if (UNIT_NOT_MM.search(t) or RE_SCALE.match(t) or RE_LONG_ID.match(t)
            or RE_YEAR.match(t)):
        return []

    m = RE_BASIC.match(t)
    if m:
        return [mk(parse_number(m.group(1)), DimKind.LINEAR, is_basic=True)]

    m = RE_LIMITS.match(t)
    if m:
        return [mk(parse_number(m.group(1)), DimKind.LINEAR,
                   tol_plus=parse_number(m.group(2)),
                   tol_minus=-parse_number(m.group(3)))]

    m = RE_LINEAR.match(t)
    if m:
        value, fit, tol = m.group(1), m.group(2), m.group(3)
        tol_v = _num_or_none(tol)
        return [mk(parse_number(value), DimKind.LINEAR, fit=fit or "",
                   tol_plus=tol_v, tol_minus=-tol_v if tol_v else None)]
    return []


def estimate_envelope(dims: list[DimValue], top_n: int = 6) -> list[float]:
    """Schätzt die Hüllmaß-Kandidaten der Zeichnung.

    Liefert die größten `top_n` voneinander verschiedenen Werte aus linearen
    Maßen und Durchmessern, absteigend sortiert. Die größten konsistenten
    Maße dominieren erfahrungsgemäß die Außenkontur.
    """
    candidates = sorted(
        {round(d.value, 2) for d in dims
         if d.kind in (DimKind.LINEAR, DimKind.DIAMETER)},
        reverse=True,
    )
    return candidates[:top_n]


def hole_pattern(dims: list[DimValue]) -> dict[float, int]:
    """Bohrbild aus der Zeichnung: {Durchmesser: Anzahl}.

    Mehrfachnennungen desselben Durchmessers werden aufsummiert
    ("4×⌀18" und später nochmal "2×⌀18" ergibt 6).
    """
    pattern: dict[float, int] = {}
    for d in dims:
        if d.kind is DimKind.DIAMETER:
            key = round(d.value, 2)
            pattern[key] = pattern.get(key, 0) + d.count
    return pattern
