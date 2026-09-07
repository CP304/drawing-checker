"""Die Zeichnung lesen: PDF, Metadaten, Masse, Form- und Lagetoleranzen.

Alles, was aus der PDF Rohdaten macht - noch ohne jede Bewertung. Die
Bewertung passiert in den pruef_*-Modulen.
"""
from __future__ import annotations

# ======================================================================
# pdfdoc
# ======================================================================
# Zugriff auf das Zeichnungs-PDF: Textlayer, Vektoren, Rendering.
#
# Alle Koordinaten sind PDF-Punkte im PyMuPDF-Koordinatensystem
# (Ursprung oben links). Die Annotation rechnet später mit demselben
# Rendering-Zoom, daher bleiben Findings lagerichtig.



import logging
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from .kern import BBox

log = logging.getLogger(__name__)

RENDER_DPI = 200
# Ab so vielen Zeichen gilt eine Seite als „hat Textlayer". Darunter wird
# sie als Scan behandelt und per OCR nachgezogen.
MIN_PAGE_CHARS = 20


@dataclass
class TextBlock:
    """Zusammenhängender Textblock mit Position."""

    text: str
    bbox: BBox
    page: int


@dataclass
class Word:
    """Ein Wort mit Fundstelle.

    conf ist die OCR-Konfidenz in Prozent; Wörter aus dem Textlayer sind
    per Definition sicher (100). Die Maßextraktion nutzt den Wert, um
    unsichere OCR-Schnipsel nicht als Maß zu übernehmen.
    """

    text: str
    bbox: BBox
    page: int
    conf: float = 100.0


class DrawingPdf:
    """Ein geöffnetes Zeichnungs-PDF mit extrahiertem Text."""

    def __init__(self, path: Path):
        self.path = path
        self.doc = pymupdf.open(path)
        self.ocr_used = False
        self.ocr_pages: list[int] = []      # 0-basierte Seiten aus OCR
        self.ocr_conf: float = 0.0          # mittlere Konfidenz in Prozent
        self._words: list[Word] | None = None
        self._blocks: list[TextBlock] | None = None

    def close(self) -> None:
        self.doc.close()

    def __enter__(self) -> "DrawingPdf":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------ Text
    @property
    def page_count(self) -> int:
        return self.doc.page_count

    def has_text_layer(self, min_chars: int = 40) -> bool:
        total = sum(len(page.get_text("text").strip()) for page in self.doc)
        return total >= min_chars

    def words(self) -> list[Word]:
        """Alle Wörter mit Bounding-Box; nutzt OCR-Fallback bei Bedarf."""
        if self._words is None:
            self._extract()
        return self._words or []

    def blocks(self) -> list[TextBlock]:
        """Textblöcke (für Sprach-Check und Schriftfeld-Analyse)."""
        if self._blocks is None:
            self._extract()
        return self._blocks or []

    def ocr_note(self) -> str:
        """Kurzbeschreibung der OCR-Güte für Bericht und Finding."""
        if not self.ocr_used:
            return ""
        seiten = ", ".join(str(p + 1) for p in self.ocr_pages)
        anzahl = sum(1 for w in self.words() if w.conf < 100.0)
        return (f"OCR auf Seite {seiten}: {anzahl} Wörter, mittlere "
                f"Erkennungsgüte {self.ocr_conf:.0f} %")

    def full_text(self) -> str:
        return "\n".join(b.text for b in self.blocks())

    def _extract(self) -> None:
        """Text je Seite holen; Seiten ohne Textlayer per OCR nachziehen.

        Gemischte Dokumente sind der Normalfall aus Archiven: Blatt 1 ist
        ein Scan, Blatt 2 stammt aus dem CAD – oder das Schriftfeld ist
        Text und die Zeichnung ein eingebettetes Rasterbild. Deshalb wird
        seitenweise entschieden und beides zusammengeführt, statt das
        ganze Dokument als „mit" oder „ohne" Textlayer zu behandeln.
        """
        self._words, self._blocks = [], []
        scanned: list[int] = []
        for pno, page in enumerate(self.doc):
            text = page.get_text("text").strip()
            if len(text) >= MIN_PAGE_CHARS:
                self._read_page_text(pno, page)
            else:
                scanned.append(pno)

        if not scanned:
            return
        from .ocr import ocr_words # später Import: Tesseract optional

        if self._words:
            log.warning("%s: Seite(n) %s ohne Textlayer – OCR nur dafür",
                        self.path.name,
                        ", ".join(str(p + 1) for p in scanned))
        else:
            log.warning("%s: kein Textlayer, versuche OCR", self.path.name)
        words = ocr_words(self.doc, pages=scanned)
        if words is None:
            log.error("%s: kein Textlayer und kein OCR verfügbar",
                      self.path.name)
            return
        self.ocr_used = True
        self.ocr_pages = scanned
        if words:
            self.ocr_conf = sum(w.conf for w in words) / len(words)
        self._words.extend(words)
        self._blocks.extend(_words_to_blocks(words))

    def _read_page_text(self, pno: int, page) -> None:
        for x0, y0, x1, y1, wtext, *_ in page.get_text("words"):
            self._words.append(Word(wtext, BBox(x0, y0, x1, y1), pno))
        for x0, y0, x1, y1, btext, _bno, btype in page.get_text("blocks"):
            if btype == 0 and btext.strip():
                self._blocks.append(
                    TextBlock(btext.strip(), BBox(x0, y0, x1, y1), pno))

    # ------------------------------------------------------------- Rendering
    def render_page(self, page: int = 0, dpi: int = RENDER_DPI) -> "pymupdf.Pixmap":
        return self.doc[page].get_pixmap(dpi=dpi)

    def page_size(self, page: int = 0) -> tuple[float, float]:
        r = self.doc[page].rect
        return (r.width, r.height)

    # ---------------------------------------------------------------- Suchen
    def search(self, needle: str, page: int | None = None) -> list[tuple[int, BBox]]:
        """Case-insensitive Volltextsuche, liefert (Seite, BBox) je Treffer."""
        hits: list[tuple[int, BBox]] = []
        pages = range(self.page_count) if page is None else [page]
        for pno in pages:
            for rect in self.doc[pno].search_for(needle):
                hits.append((pno, BBox(rect.x0, rect.y0, rect.x1, rect.y1)))
        return hits


def _words_to_blocks(words: list[Word], line_tol: float = 6.0) -> list[TextBlock]:
    """Gruppiert OCR-Wörter zeilenweise zu Blöcken (grobe Näherung)."""
    blocks: list[TextBlock] = []
    by_page: dict[int, list[Word]] = {}
    for w in words:
        by_page.setdefault(w.page, []).append(w)
    for pno, ws in by_page.items():
        ws.sort(key=lambda w: (round(w.bbox.y0 / line_tol), w.bbox.x0))
        line: list[Word] = []
        for w in ws:
            if line and abs(w.bbox.y0 - line[-1].bbox.y0) > line_tol:
                blocks.append(_merge_line(line, pno))
                line = []
            line.append(w)
        if line:
            blocks.append(_merge_line(line, pno))
    return blocks


def _merge_line(line: list[Word], pno: int) -> TextBlock:
    text = " ".join(w.text for w in line)
    bbox = BBox(
        min(w.bbox.x0 for w in line),
        min(w.bbox.y0 for w in line),
        max(w.bbox.x1 for w in line),
        max(w.bbox.y1 for w in line),
    )
    return TextBlock(text, bbox, pno)


# ======================================================================
# metadata
# ======================================================================
# Metadaten aus der Zeichnung: letztes Änderungsdatum.
#
# Strategie: Alle Datumsangaben im Textlayer einsammeln (deutsche, ISO- und
# US-Schreibweise) und das SPÄTESTE nehmen – das ist auf Fertigungszeichnungen
# praktisch immer der jüngste Eintrag der Änderungstabelle bzw. das
# Freigabedatum. Fallback: Änderungsdatum aus den PDF-Metadaten.



import datetime as dt
import logging
import re


RE_DMY = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b")        # 12.01.2026
RE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")                # 2026-01-12
RE_US = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")           # 5/23/2021
RE_PDF_DATE = re.compile(r"D:(\d{4})(\d{2})(\d{2})")

MIN_YEAR, MAX_YEAR = 1970, 2100


def _mk(year: int, month: int, day: int) -> dt.date | None:
    if year < 100:
        year += 2000 if year < 70 else 1900
    if not (MIN_YEAR <= year <= MAX_YEAR):
        return None
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def _candidates(text: str):
    for d, m, y in RE_DMY.findall(text):
        date = _mk(int(y), int(m), int(d))
        if date:
            yield date
    for y, m, d in RE_ISO.findall(text):
        date = _mk(int(y), int(m), int(d))
        if date:
            yield date
    for a, b, y in RE_US.findall(text):
        a, b = int(a), int(b)
        # US-Schreibweise ist Monat/Tag; wenn das unmöglich ist, Tag/Monat.
        date = _mk(int(y), a, b) if a <= 12 else None
        if date is None and b <= 12:
            date = _mk(int(y), b, a)
        if date:
            yield date


def extract_revision_date(pdf) -> str:
    """Spätestes Datum auf der Zeichnung als ISO-String; '' wenn keins.

    pdf: DrawingPdf. Nutzt den Textlayer; Fallback sind die PDF-Metadaten
    (ModDate/CreationDate), dann mit Kennzeichnung "(PDF-Metadatum)".
    """
    dates = list(_candidates(pdf.full_text()))
    if dates:
        return max(dates).isoformat()

    meta = pdf.doc.metadata or {}
    for key in ("modDate", "creationDate"):
        m = RE_PDF_DATE.search(meta.get(key) or "")
        if m:
            date = _mk(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if date:
                return f"{date.isoformat()} (PDF-Metadatum)"
    return ""


# --------------------------------------------------------------------------
# Gewichtsangabe aus dem Schriftfeld
# --------------------------------------------------------------------------
RE_WEIGHT = re.compile(
    r"(\d{1,6}(?:[.,]\d{1,3})?)\s*(kg|g|t)\b(?!\w)", re.IGNORECASE)
# Zeilen, in denen eine Masseangabe erwartet wird (verhindert Treffer auf
# Werkstoffnamen o. Ä.).
RE_WEIGHT_LABEL = re.compile(
    r"gewicht|masse\b|weight|mass\b", re.IGNORECASE)
_TO_KG = {"kg": 1.0, "g": 0.001, "t": 1000.0}


# Rohteil-/Fertigteilgewicht unterscheiden: verglichen wird mit dem
# FERTIGGEWICHT, weil das STEP-Modell das fertige Teil beschreibt.
RE_ROUGH_WEIGHT = re.compile(
    r"rohteil|rohgewicht|rohmasse|brutto|gross\s*(?:weight|mass)|raw",
    re.IGNORECASE)


def extract_weight_kg(pdf) -> float | None:
    """Masseangabe der Zeichnung in kg; None wenn keine gefunden.

    Reihenfolge der Bevorzugung:
      1. Angaben in Textblöcken mit Gewichts-Label (Schriftfeld), die NICHT
         als Rohteil-/Bruttogewicht gekennzeichnet sind – das ist das
         Fertiggewicht und damit der richtige Vergleichswert zum Modell.
      2. Sonstige beschriftete Angaben (auch Rohgewicht).
      3. Freistehende Einheiten-Angaben im Text.
    """
    finished: list[float] = []
    labelled: list[float] = []
    loose: list[float] = []
    for block in pdf.blocks():
        has_label = bool(RE_WEIGHT_LABEL.search(block.text))
        is_rough = bool(RE_ROUGH_WEIGHT.search(block.text))
        for value, unit in RE_WEIGHT.findall(block.text):
            kg = _to_kg(value, unit)
            if kg is None:
                continue
            if has_label and not is_rough:
                finished.append(kg)
            elif has_label:
                labelled.append(kg)
            else:
                loose.append(kg)
    for pool in (finished, labelled, loose):
        if pool:
            return max(pool)
    return None


def _to_kg(value: str, unit: str) -> float | None:
    try:
        v = float(value.replace(",", "."))
    except ValueError:
        return None
    kg = v * _TO_KG[unit.lower()]
    # Plausibilitätsfenster: 1 g bis 50 t
    return kg if 0.001 <= kg <= 50000 else None


# --------------------------------------------------------------------------
# Maßstab aus dem Schriftfeld
# --------------------------------------------------------------------------
_SC_NUM = r"(\d{1,3}(?:[.,]\d{1,2})?)"
RE_SCALE = re.compile(
    rf"(?:ma[ßs]stab|scale)\s*:?\s*{_SC_NUM}\s*[:/]\s*{_SC_NUM}",
    re.IGNORECASE)
_PT_PER_MM = 72.0 / 25.4


# Normübliche Maßstäbe nach ISO 5455 (plus die gängigen Zwischenwerte).
COMMON_SCALES = {
    0.02, 0.05, 0.1, 0.2, 0.5,          # Vergrößerungen 50:1 … 2:1
    1.0,
    2.0, 2.5, 4.0, 5.0, 10.0, 20.0, 25.0, 50.0, 100.0, 200.0,
}


def extract_scale(pdf) -> float | None:
    """Maßstab als Faktor Bauteil/Zeichnung.

    „1:2" (verkleinert) -> 2.0, „2:1" (vergrößert) -> 0.5, „1:1" -> 1.0.
    Ausgewertet wird nur die BESCHRIFTETE Angabe („Maßstab 1:2", „SCALE 1:2")
    und nur, wenn sie einem normüblichen Maßstab entspricht – freistehende
    „x:y"-Muster auf einer Zeichnung sind häufiger Blatt-, Zeit- oder
    Verhältnisangaben als Maßstäbe.
    """
    for a, b in RE_SCALE.findall(pdf.full_text()):
        try:
            num = float(a.replace(",", "."))
            den = float(b.replace(",", "."))
        except ValueError:
            continue
        if num <= 0 or den <= 0:
            continue
        factor = den / num
        if any(abs(factor - c) < 0.01 for c in COMMON_SCALES):
            return factor
    return None


def mm_per_point(scale_factor: float) -> float:
    """Bauteil-Millimeter je PDF-Punkt bei gegebenem Maßstab."""
    return scale_factor / _PT_PER_MM


# ======================================================================
# dimensions
# ======================================================================
# Extraktion von Maßangaben aus dem Zeichnungs-PDF.
#
# Grundlage für den Geometrieabgleich gegen STEP und für die Bemaßungs-/
# Fertigungsregeln. Die Extraktion ist bewusst konservativ – lieber ein Maß
# übersehen als eine Normbezeichnung ("ISO 2768") als 2768-mm-Maß
# fehlinterpretieren.
#
# Erfasst je Maß:
#   * Nennwert und Art (linear, Durchmesser, Radius, Gewinde)
#   * Wiederholfaktor ("4×⌀18" -> count=4)
#   * Toleranz (±0,1 -> tol_plus/tol_minus; Grenzabmaße +0,2/-0,1)
#   * ISO-Passung ("40H7" -> fit="H7") inkl. IT-Grad
#   * theoretisch genaues Maß (eingerahmt, ISO 1101) -> is_basic



import os
import re
from dataclasses import dataclass
from enum import Enum

from .kern import BBox


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
# Wörter, nach denen eine Zahl keine Länge ist (Gewicht, Stückzahl, Härte).
NON_DIM_PREV = {"gewicht", "masse", "weight", "mass", "gew", "menge",
                "stück", "stk", "anzahl", "qty", "pos", "position",
                "härte", "hardness", "index", "rev", "revision", "blatt",
                "sheet", "seite", "page", "zone", "auftrag", "order"}
# Einheiten, die als eigenes Folgewort stehen und ein Längenmaß ausschließen.
RE_UNIT_AFTER = re.compile(
    r"^(kg|kgs|g|t|lb|lbs|°|grad|deg|%|µm|um|hrc|hv|hb|n/mm|mpa|bar|nm|min|"
    r"stk|stück|pcs|pc)\b", re.IGNORECASE)
# Ein Token wie "1:2" ist ein Massstab, kein Mass. Der Name ist bewusst
# ein anderer als der von RE_SCALE oben: der sucht die Massstabsangabe
# im Schriftfeld, dieser wehrt ein Token in der Massextraktion ab.
RE_SCALE_TOKEN = re.compile(r"^\d+\s*:\s*\d+$")
RE_LONG_ID = re.compile(r"^\d{6,}$")
RE_YEAR = re.compile(r"^(19|20)\d{2}$")


def parse_number(s: str) -> float:
    return float(s.replace(",", "."))


def _num_or_none(s) -> float | None:
    return parse_number(s) if s else None


# Mindestkonfidenz für Maße aus OCR. Kurze Zahlenschnipsel ("2", "13")
# sind die häufigste OCR-Halluzination und würden als Maß den
# Geometrieabgleich verfälschen – deshalb für sie eine höhere Schwelle.
OCR_DIM_MIN_CONF = float(os.environ.get("DRAWING_CHECKER_OCR_DIM_CONF", 70))
OCR_SHORT_MIN_CONF = float(os.environ.get("DRAWING_CHECKER_OCR_SHORT_CONF", 85))


def extract_dimensions(pdf: DrawingPdf, max_plausible: float = 6000.0
                       ) -> list[DimValue]:
    """Extrahiert alle Maßkandidaten aus den Wörtern des PDFs.

    Bei OCR-Text werden unsichere Funde verworfen (siehe Word.conf) –
    lieber ein Maß weniger als ein erfundenes.
    """
    words = pdf.words()
    dims: list[DimValue] = []
    for i, w in enumerate(words):
        if not _confident_enough(w):
            continue
        prev = words[i - 1].text.lower().rstrip(".:") if i > 0 else ""
        # Nachbarwörter für Kontextangaben (Tiefe, Grenzabmaße, Faktor)
        nxt = " ".join(x.text for x in words[i + 1:i + 3])
        for d in _parse_word(w, prev_word=prev, next_text=nxt):
            if 0.05 <= d.value <= max_plausible:
                dims.append(d)
    return dims


def _confident_enough(w: Word) -> bool:
    conf = getattr(w, "conf", 100.0)
    if conf >= 100.0:
        return True
    limit = (OCR_SHORT_MIN_CONF if len(w.text.strip()) <= 2
             else OCR_DIM_MIN_CONF)
    return conf >= limit


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
    if prev_word in NORM_WORDS or prev_word in NON_DIM_PREV:
        return []
    # „4200" gefolgt von „kg" ist ein Gewicht, keine Länge. CAD-Systeme
    # trennen Zahl und Einheit häufig in zwei Wörter.
    first_next = next_text.split()[:1]
    if first_next and RE_UNIT_AFTER.match(first_next[0]):
        return []
    if (UNIT_NOT_MM.search(t) or RE_SCALE_TOKEN.match(t) or RE_LONG_ID.match(t)
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


# ======================================================================
# fcf
# ======================================================================
# Erkennung von Toleranzrahmen (Feature Control Frames) als Vektorgrafik.
#
# Hintergrund: CAD-Systeme zeichnen Toleranzrahmen samt GD&T-Symbol meist als
# Grafik. Im PDF-Textlayer stehen dann nur Toleranzwert und Bezugsbuchstaben –
# das Symbol fehlt. Symbolbasierte Regeln wären damit auf realen Zeichnungen
# blind.
#
# Dieses Modul findet die Rahmen über ihre Geometrie (flaches Rechteck aus
# Linien, Text darin) und liest Wert und Bezüge aus. Das Symbol selbst bleibt
# unbekannt – dafür meldet der Checker einen Sichtprüfungs-Hinweis.



import re
from dataclasses import dataclass, field

from .kern import BBox

# Geometrie eines Toleranzrahmens (PDF-Punkte).
MIN_H, MAX_H = 5.0, 24.0
MIN_W, MAX_W = 14.0, 300.0
MIN_RATIO = 1.4

RE_VALUE = re.compile(r"^[⌀Øø]?\s*\d+(?:[.,]\d+)?$")
RE_DATUM_LETTER = re.compile(r"^[A-Z](?:[ⓂⓁ])?$")
RE_MODIFIER = re.compile(r"[ⓂⓁⒺⓅ]")


@dataclass
class FeatureFrame:
    """Ein erkannter Toleranzrahmen."""

    bbox: BBox
    page: int
    texts: list[str] = field(default_factory=list)
    value: float | None = None
    diameter_zone: bool = False       # ⌀-Toleranzzone
    datums: list[str] = field(default_factory=list)
    symbol: str = ""                  # nur gesetzt, wenn im Textlayer
    chambers: int = 0

    @property
    def has_datums(self) -> bool:
        return bool(self.datums)

    @property
    def raw(self) -> str:
        return " ".join(self.texts)


def find_feature_frames(pdf, max_pages: int = 3) -> list[FeatureFrame]:
    """Sucht Toleranzrahmen auf den ersten Seiten des Dokuments."""
    frames: list[FeatureFrame] = []
    for pno in range(min(pdf.page_count, max_pages)):
        page = pdf.doc[pno]
        words = page.get_text("words")
        for path in page.get_drawings():
            rect = path.get("rect")
            if rect is None:
                continue
            h, w = rect.height, rect.width
            if not (MIN_H <= h <= MAX_H and MIN_W <= w <= MAX_W):
                continue
            if w / max(h, 0.1) < MIN_RATIO:
                continue
            inside = [
                wd for wd in words
                if rect.x0 - 1 <= (wd[0] + wd[2]) / 2 <= rect.x1 + 1
                and rect.y0 - 1 <= (wd[1] + wd[3]) / 2 <= rect.y1 + 1
            ]
            if not inside:
                continue
            texts = [wd[4].strip() for wd in sorted(inside, key=lambda x: x[0])]
            if not any(any(c.isdigit() for c in t) for t in texts):
                continue
            frame = _parse_frame(texts, rect, pno, len(path["items"]))
            if frame is not None:
                frames.append(frame)
    return _dedupe(frames)


def _parse_frame(texts: list[str], rect, pno: int,
                 n_items: int) -> FeatureFrame | None:
    """Wandelt die Textfragmente eines Rahmens in Wert + Bezüge um."""
    value: float | None = None
    diameter = False
    datums: list[str] = []
    symbol = ""
    for t in texts:
        clean = t.strip()
        if not clean:
            continue
        if RE_VALUE.match(clean):
            if value is None:
                diameter = clean[0] in "⌀Øø"
                try:
                    value = float(re.sub(r"[^\d.,]", "", clean)
                                  .replace(",", "."))
                except ValueError:
                    pass
            continue
        if RE_DATUM_LETTER.match(clean):
            letter = clean[0]
            if letter not in datums:
                datums.append(letter)
            continue
        # GD&T-Symbol im Textlayer (selten, aber möglich)
        for ch in clean:
            if ch in "⌖⏥⏤○⌭∥⊥∠↗⌰◎⌯⌓⌔":
                symbol = ch
    if value is None:
        return None
    return FeatureFrame(
        bbox=BBox(rect.x0, rect.y0, rect.x1, rect.y1), page=pno,
        texts=texts, value=value, diameter_zone=diameter, datums=datums,
        symbol=symbol, chambers=max(1, n_items - 3),
    )


def _contains(outer: FeatureFrame, inner: FeatureFrame,
              slack: float = 2.0) -> bool:
    a, b = outer.bbox, inner.bbox
    return (outer.page == inner.page
            and a.x0 - slack <= b.x0 and a.y0 - slack <= b.y0
            and a.x1 + slack >= b.x1 and a.y1 + slack >= b.y1)


def _dedupe(frames: list[FeatureFrame]) -> list[FeatureFrame]:
    """Entfernt Mehrfachtreffer und Teilkammern desselben Rahmens.

    CAD-Exporte zeichnen Toleranzrahmen als mehrere Pfade: den ganzen
    Rahmen und einzelne Kammern. Der umfassendste Rahmen enthält alle
    Angaben (Wert plus Bezüge) und gewinnt.
    """
    # Größte zuerst – kleinere, enthaltene Rahmen fallen dann weg.
    ordered = sorted(
        frames, key=lambda f: (f.bbox.x1 - f.bbox.x0) * (f.bbox.y1 - f.bbox.y0),
        reverse=True)
    out: list[FeatureFrame] = []
    for f in ordered:
        if any(_contains(g, f) for g in out):
            continue
        out.append(f)
    return sorted(out, key=lambda f: (f.page, f.bbox.y0, f.bbox.x0))
