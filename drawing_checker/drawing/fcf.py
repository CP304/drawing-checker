"""Erkennung von Toleranzrahmen (Feature Control Frames) als Vektorgrafik.

Hintergrund: CAD-Systeme zeichnen Toleranzrahmen samt GD&T-Symbol meist als
Grafik. Im PDF-Textlayer stehen dann nur Toleranzwert und Bezugsbuchstaben –
das Symbol fehlt. Symbolbasierte Regeln wären damit auf realen Zeichnungen
blind.

Dieses Modul findet die Rahmen über ihre Geometrie (flaches Rechteck aus
Linien, Text darin) und liest Wert und Bezüge aus. Das Symbol selbst bleibt
unbekannt – dafür meldet der Checker einen Sichtprüfungs-Hinweis.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..core.models import BBox

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
