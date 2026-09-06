"""Metadaten aus der Zeichnung: letztes Änderungsdatum.

Strategie: Alle Datumsangaben im Textlayer einsammeln (deutsche, ISO- und
US-Schreibweise) und das SPÄTESTE nehmen – das ist auf Fertigungszeichnungen
praktisch immer der jüngste Eintrag der Änderungstabelle bzw. das
Freigabedatum. Fallback: Änderungsdatum aus den PDF-Metadaten.
"""
from __future__ import annotations

import datetime as dt
import logging
import re

log = logging.getLogger(__name__)

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


def extract_weight_kg(pdf) -> float | None:
    """Masseangabe der Zeichnung in kg; None wenn keine gefunden.

    Bevorzugt Angaben in Textblöcken mit Gewichts-Label (Schriftfeld);
    fällt sonst auf die erste plausible Einheiten-Angabe zurück.
    """
    labelled: list[float] = []
    loose: list[float] = []
    for block in pdf.blocks():
        has_label = bool(RE_WEIGHT_LABEL.search(block.text))
        for value, unit in RE_WEIGHT.findall(block.text):
            kg = _to_kg(value, unit)
            if kg is None:
                continue
            (labelled if has_label else loose).append(kg)
    for pool in (labelled, loose):
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
