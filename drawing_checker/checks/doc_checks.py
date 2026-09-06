"""Dokumenten-Formalien: Vollständigkeit und Beherrschbarkeit der Datei.

Fehler, die nichts mit der Konstruktion zu tun haben, aber im Einkauf
regelmäßig zu Rückfragen, Nachträgen oder falsch gefertigten Teilen führen:

  DOC.SHEET_COUNT  „Blatt 1 von 3", geliefert wird 1 Seite – die Zeichnung
                   ist unvollständig; die fehlenden Blätter enthalten oft
                   genau die Toleranz- und Schweißangaben.
  DOC.ANNOTATIONS  Das PDF enthält nachträgliche Kommentare, Stempel oder
                   Freihandmarkierungen. Solche Rotstiftänderungen sind
                   nicht Teil des freigegebenen Standes.
  DOC.DATE_FUTURE  Datum auf der Zeichnung liegt in der Zukunft oder
                   unplausibel weit zurück – Hinweis auf Tippfehler im
                   Änderungsstand.
  DOC.DECIMAL_MIXED Dezimalkomma und Dezimalpunkt gemischt. Für einen
                   internationalen Lieferanten ein echtes Risiko
                   („1.500" = 1,5 oder 1500?).
"""
from __future__ import annotations

import datetime as _dt
import logging
import re

from ..core.models import BBox
from .base import CheckContext

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
    from ..drawing.metadata import _candidates      # gemeinsame Datumslogik

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
