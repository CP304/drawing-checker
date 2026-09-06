"""Annotation des Zeichnungsbildes: Marker an den Fundstellen + Legende.

Das PDF wird hochauflösend gerendert; Findings mit bbox bekommen nummerierte
farbige Marker, alle Findings erscheinen in einer Legendenspalte rechts.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..core.models import Finding, MaterialResult, Severity, SEVERITY_LABEL
from ..drawing.pdfdoc import RENDER_DPI, DrawingPdf

log = logging.getLogger(__name__)

COLORS = {
    Severity.INFO: (70, 130, 180),      # Stahlblau
    Severity.WARNING: (230, 145, 0),    # Orange
    Severity.ERROR: (200, 30, 30),      # Rot
    Severity.BLOCKER: (140, 0, 140),    # Violett (K.O.)
}
LEGEND_WIDTH = 560
PAD = 14


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def annotate(pdf: DrawingPdf, result: MaterialResult, out_path: Path,
             dpi: int = RENDER_DPI) -> Path:
    """Rendert Seite 0 (und weitere Seiten mit Findings) und annotiert sie.

    Mehrseitige PDFs: Es wird je Seite mit Findings ein Bild erzeugt, Seite 0
    immer. Rückgabe ist der Pfad des Bildes zu Seite 0; weitere Seiten hängen
    "_s2", "_s3" … an.
    """
    pages = sorted({f.page for f in result.findings if f.bbox} | {0})
    scale = dpi / 72.0
    first: Path | None = None
    for page in pages:
        pix = pdf.render_page(page, dpi=dpi)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        canvas = _draw_page(img, result, page, scale)
        path = out_path if page == 0 else out_path.with_stem(
            f"{out_path.stem}_s{page + 1}")
        canvas.save(path)
        # Bilder ausdrücklich schließen: eine A1-Seite bei 200 dpi sind rund
        # 100 MB Rohdaten; im Dauerlauf summiert sich das sonst auf.
        canvas.close()
        img.close()
        pix = None
        if page == 0:
            first = path
    assert first is not None
    return first


def _draw_page(img: Image.Image, result: MaterialResult, page: int,
               scale: float) -> Image.Image:
    findings = result.sorted_findings()
    canvas = Image.new("RGB", (img.width + LEGEND_WIDTH, img.height), "white")
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)
    f_marker = _font(26)
    f_head = _font(24)
    f_text = _font(17)

    # Marker auf der Zeichnung (nur Findings dieser Seite mit Position)
    for idx, finding in enumerate(findings, start=1):
        if finding.bbox is None or finding.page != page:
            continue
        color = COLORS[finding.severity]
        x0, y0, x1, y1 = (v * scale for v in finding.bbox.as_tuple())
        m = 6
        draw.rectangle([x0 - m, y0 - m, x1 + m, y1 + m], outline=color, width=4)
        r = 20
        cx, cy = x1 + m + r + 4, max(y0 - m, r + 2)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
        draw.text((cx, cy), str(idx), font=f_marker, fill="white", anchor="mm")

    # Status-Stempel oben links (Gesamturteil auf einen Blick)
    if page == 0:
        worst = result.worst_severity
        if worst is None or worst <= Severity.INFO:
            stamp, color = "OK", (47, 125, 50)
        else:
            stamp = {Severity.WARNING: "PRÜFEN", Severity.ERROR: "FEHLER",
                     Severity.BLOCKER: "K.O."}[worst]
            color = COLORS[worst]
        f_stamp = _font(34)
        text = f" {stamp} · {result.material} "
        tw = draw.textlength(text, font=f_stamp)
        draw.rectangle([16, 16, 16 + tw + 12, 70], outline=color, width=5)
        draw.text((22, 26), text, font=f_stamp, fill=color)

    # Legende rechts
    lx = img.width + PAD
    y = PAD
    draw.rectangle([img.width, 0, canvas.width - 1, canvas.height - 1],
                   outline=(180, 180, 180), width=1)
    draw.text((lx, y), f"Prüfergebnis  {result.material}", font=f_head, fill="black")
    y += 40
    if not findings:
        draw.text((lx, y), "Keine Beanstandungen.", font=f_text, fill=(0, 120, 0))
    for idx, finding in enumerate(findings, start=1):
        color = COLORS[finding.severity]
        marker = f"{idx}." if finding.bbox is not None else "–"
        tag = SEVERITY_LABEL[finding.severity]
        lines = _wrap(f"{marker} [{tag}] {finding.code}: {finding.text}",
                      f_text, LEGEND_WIDTH - 2 * PAD, draw)
        for line in lines:
            if y > canvas.height - 30:
                draw.text((lx, y), "… (weitere siehe Excel)", font=f_text,
                          fill="black")
                return canvas
            draw.text((lx, y), line, font=f_text, fill=color)
            y += 22
        y += 6
    if result.step_summary:
        y += 10
        for line in _wrap("Geometrie: " + result.step_summary, f_text,
                          LEGEND_WIDTH - 2 * PAD, draw):
            if y > canvas.height - 30:
                break
            draw.text((lx, y), line, font=f_text, fill=(60, 60, 60))
            y += 22
    return canvas


def _wrap(text: str, font, width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        probe = (cur + " " + w).strip()
        if draw.textlength(probe, font=font) <= width:
            cur = probe
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines
