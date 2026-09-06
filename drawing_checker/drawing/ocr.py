"""OCR-Fallback für gescannte Zeichnungen ohne Textlayer (Tesseract, deu+eng)."""
from __future__ import annotations

import logging

import pymupdf

from ..core.models import BBox
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pdfdoc import Word

log = logging.getLogger(__name__)

OCR_DPI = 300


def ocr_words(doc: "pymupdf.Document") -> "list[Word] | None":
    """OCR über alle Seiten; None, wenn Tesseract nicht verfügbar ist.

    Liefert Wort-Bounding-Boxen in PDF-Punkten, damit sie mit dem
    Textlayer-Pfad austauschbar sind.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        log.warning("pytesseract nicht installiert – OCR-Fallback nicht verfügbar")
        return None
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        log.warning("Tesseract-Binary nicht gefunden – OCR-Fallback nicht verfügbar")
        return None

    from .pdfdoc import Word  # Laufzeitimport, Zyklusfrei

    scale = 72.0 / OCR_DPI
    words: list[Word] = []
    for pno, page in enumerate(doc):
        pix = page.get_pixmap(dpi=OCR_DPI, colorspace=pymupdf.csGRAY)
        img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        data = pytesseract.image_to_data(
            img, lang="deu+eng", output_type=pytesseract.Output.DICT
        )
        for i, text in enumerate(data["text"]):
            text = text.strip()
            if not text or int(data["conf"][i]) < 40:
                continue
            x, y = data["left"][i] * scale, data["top"][i] * scale
            w, h = data["width"][i] * scale, data["height"][i] * scale
            words.append(Word(text, BBox(x, y, x + w, y + h), pno))
    log.info("OCR: %d Wörter erkannt", len(words))
    return words
