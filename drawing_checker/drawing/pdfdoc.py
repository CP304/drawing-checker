"""Zugriff auf das Zeichnungs-PDF: Textlayer, Vektoren, Rendering.

Alle Koordinaten sind PDF-Punkte im PyMuPDF-Koordinatensystem
(Ursprung oben links). Die Annotation rechnet später mit demselben
Rendering-Zoom, daher bleiben Findings lagerichtig.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from ..core.models import BBox

log = logging.getLogger(__name__)

RENDER_DPI = 200


@dataclass
class TextBlock:
    """Zusammenhängender Textblock mit Position."""

    text: str
    bbox: BBox
    page: int


@dataclass
class Word:
    text: str
    bbox: BBox
    page: int


class DrawingPdf:
    """Ein geöffnetes Zeichnungs-PDF mit extrahiertem Text."""

    def __init__(self, path: Path):
        self.path = path
        self.doc = pymupdf.open(path)
        self.ocr_used = False
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

    def full_text(self) -> str:
        return "\n".join(b.text for b in self.blocks())

    def _extract(self) -> None:
        self._words, self._blocks = [], []
        if self.has_text_layer():
            for pno, page in enumerate(self.doc):
                for x0, y0, x1, y1, wtext, *_ in page.get_text("words"):
                    self._words.append(Word(wtext, BBox(x0, y0, x1, y1), pno))
                for x0, y0, x1, y1, btext, _bno, btype in page.get_text("blocks"):
                    if btype == 0 and btext.strip():
                        self._blocks.append(
                            TextBlock(btext.strip(), BBox(x0, y0, x1, y1), pno)
                        )
            return
        # Kein Textlayer: OCR-Fallback (falls Tesseract verfügbar).
        from .ocr import ocr_words  # später Import: Tesseract optional

        log.warning("%s: kein Textlayer, versuche OCR", self.path.name)
        words = ocr_words(self.doc)
        if words is not None:
            self.ocr_used = True
            self._words = words
            self._blocks = _words_to_blocks(words)
        else:
            log.error("%s: kein Textlayer und kein OCR verfügbar", self.path.name)

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
