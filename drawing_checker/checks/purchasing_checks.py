"""Prüfung aus Sicht des internationalen Einkaufs.

Die Zeichnung muss für einen Lieferanten ausreichen, der weder im Haus
sitzt noch die Historie des Teils kennt. Geprüft wird deshalb nicht nur die
technische Richtigkeit, sondern die Anfragereife:

  PUR.VAGUE_SPEC   Formulierungen ohne prüfbaren Inhalt („ca. 20", „nach
                   Absprache", „sauber entgraten", „TBD"). Sie erzeugen
                   Rückfragen, Nachträge und Streit bei der Abnahme.
  PUR.INTERNAL_NORM Verweis auf Werk-/Konzernnormen, die ein externer
                   Lieferant nicht beziehen kann. Sie müssen der Anfrage
                   als Dokument beiliegen.
  PUR.STOCK_SIZE   Blechdicke oder Rundmaterial außerhalb der gängigen
                   Vorzugsmaße. Das Teil muss dann aus dem nächstgrößeren
                   Halbzeug herausgearbeitet werden – teurer, längere
                   Lieferzeit, oft ohne konstruktiven Grund.

Das Wissen steht in `rules/beschaffung*.yaml` und ist ohne Codeänderung
erweiterbar.
"""
from __future__ import annotations

import logging
import re

import yaml

from ..drawing.dimensions import DimValue
from .base import CheckContext, rules_files

log = logging.getLogger(__name__)


def _load_knowledge() -> dict:
    """Alle beschaffung*.yaml einsammeln (mitgeliefert + externe Ordner)."""
    vage: list[tuple[re.Pattern, str]] = []
    hausnormen: list[tuple[re.Pattern, str]] = []
    halbzeuge: dict[str, list[float]] = {}
    for f in rules_files("beschaffung*.yaml"):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            log.error("Beschaffungs-Wissenspaket %s nicht lesbar: %s", f, exc)
            continue
        for key, target in (("vage", vage), ("hausnormen", hausnormen)):
            for entry in data.get(key, []) or []:
                try:
                    target.append((re.compile(entry["pattern"], re.IGNORECASE),
                                   entry["message"]))
                except (KeyError, TypeError, re.error) as exc:
                    log.error("Eintrag in %s (%s) fehlerhaft: %s", f, key, exc)
        for key, values in (data.get("halbzeuge") or {}).items():
            try:
                halbzeuge.setdefault(key, []).extend(float(v) for v in values)
            except (TypeError, ValueError):
                log.error("Halbzeugliste %r in %s fehlerhaft", key, f)
    return {"vage": vage, "hausnormen": hausnormen, "halbzeuge": halbzeuge}


KNOWLEDGE = _load_knowledge()

RE_SHEET_THICK_VALUE = re.compile(
    r"(?:blechdicke|blechstärke|materialstärke|sheet\s*thickness"
    r"|thickness|dicke|\bt|\bs)\s*[:=]?\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:mm)?",
    re.IGNORECASE)
RE_ROUND_STOCK = re.compile(
    r"(?:rundstahl|rundmaterial|blankstahl|round\s*bar|stangenmaterial)"
    r"[^\n]{0,20}?(\d{1,3}(?:[.,]\d{1,2})?)", re.IGNORECASE)


def run_purchasing_checks(ctx: CheckContext, dims: list[DimValue]) -> None:
    check_vague_specs(ctx)
    check_internal_norms(ctx)
    check_stock_sizes(ctx, dims)


def check_vague_specs(ctx: CheckContext) -> None:
    """Unbestimmte Formulierungen melden – je Muster höchstens einmal."""
    if not ctx.profile.enabled("PUR.VAGUE_SPEC"):
        return
    limit = int(ctx.profile.rule_param("PUR.VAGUE_SPEC", "max_findings", 4))
    shown = 0
    for regex, message in KNOWLEDGE["vage"]:
        hit = _first_hit(ctx, regex)
        if hit is None:
            continue
        matched, bbox, page = hit
        shown += 1
        if shown > limit:
            continue
        ctx.add("PUR.VAGUE_SPEC",
                f"Unbestimmte Angabe „{matched.strip()}“: {message}",
                bbox=bbox, page=page,
                detail="Aus Sicht eines auswärtigen Lieferanten nicht "
                       "kalkulierbar und bei der Abnahme nicht prüfbar. "
                       "Anforderung mit Zahlenwert oder Norm angeben.")
    if shown > limit:
        ctx.add("PUR.VAGUE_SPEC",
                f"… und {shown - limit} weitere unbestimmte Angaben",
                detail="Vollständige Liste im Regelkatalog "
                       "(rules/beschaffung.yaml).")


def check_internal_norms(ctx: CheckContext) -> None:
    """Verweise auf nicht öffentlich beziehbare Normen melden."""
    if not ctx.profile.enabled("PUR.INTERNAL_NORM"):
        return
    seen: set[str] = set()
    for regex, message in KNOWLEDGE["hausnormen"]:
        hit = _first_hit(ctx, regex)
        if hit is None:
            continue
        matched, bbox, page = hit
        key = matched.strip().upper()
        if key in seen:
            continue
        seen.add(key)
        ctx.add("PUR.INTERNAL_NORM",
                f"Verweis auf interne Norm „{matched.strip()}“: {message}",
                bbox=bbox, page=page,
                detail="Der Anfrage beilegen oder durch eine öffentliche "
                       "Norm ersetzen – sonst liefert jeder Lieferant nach "
                       "eigener Auslegung.")


def check_stock_sizes(ctx: CheckContext, dims: list[DimValue]) -> None:
    """Blechdicke/Rundmaterial gegen die Vorzugsmaße prüfen."""
    if not ctx.profile.enabled("PUR.STOCK_SIZE"):
        return
    sheet = KNOWLEDGE["halbzeuge"].get("blech") or []
    if not sheet:
        return
    text = ctx.pdf.full_text()
    for m in RE_SHEET_THICK_VALUE.finditer(text):
        try:
            value = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        if not 0.3 <= value <= 120:
            continue
        if _matches_stock(value, sheet):
            continue
        nearest = min(sheet, key=lambda s: abs(s - value))
        ctx.add("PUR.STOCK_SIZE",
                f"Blechdicke {value:g} mm ist kein Vorzugsmaß "
                f"(nächstes Lagermaß {nearest:g} mm)",
                detail="Ein Sondermaß bedeutet Mindestabnahmemengen, längere "
                       "Lieferzeit oder Herausarbeiten aus dickerem Material. "
                       "Wenn es keinen funktionalen Grund gibt: auf das "
                       "Lagermaß gehen. Vorzugsmaße pflegbar in "
                       "rules/beschaffung.yaml.")
        break       # eine Blechmeldung je Zeichnung genügt

    _check_round_stock(ctx, text)


def _check_round_stock(ctx: CheckContext, text: str) -> None:
    """Ausdrücklich genanntes Rundmaterial gegen die Lagerdurchmesser prüfen.

    Bewusst nur bei ausgeschriebenem Halbzeug („Rundstahl ⌀37") – jeder
    beliebige Durchmesser auf der Zeichnung wäre ein Maß am Fertigteil und
    sagt nichts über das Halbzeug aus.
    """
    series = KNOWLEDGE["halbzeuge"].get("rund") or []
    if not series:
        return
    for m in RE_ROUND_STOCK.finditer(text):
        try:
            value = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        if not 3 <= value <= 300 or _matches_stock(value, series, tol=0.2):
            continue
        nearest = min(series, key=lambda s: abs(s - value))
        ctx.add("PUR.STOCK_SIZE",
                f"Rundmaterial ⌀{value:g} mm ist kein Lagermaß "
                f"(nächstes {nearest:g} mm)",
                detail="Sonderdurchmesser müssen aus dem nächstgrößeren "
                       "Stangenmaterial gedreht werden – mehr Zerspanung, "
                       "höherer Preis, längere Beschaffung.")
        return


def _matches_stock(value: float, series: list[float],
                   tol: float = 0.05) -> bool:
    return any(abs(value - s) <= tol for s in series)


def _first_hit(ctx: CheckContext, regex: re.Pattern):
    """Erster Treffer mit Fundstelle (für die Markierung im Bild)."""
    for block in ctx.pdf.blocks():
        m = regex.search(block.text)
        if m:
            return m.group(0), block.bbox, block.page
    return None
