"""Bemaßungs- und Fertigungsprüfungen.

Deckt die klassischen Bemaßungsfehler (ISO 129-1 / DIN 406) und die
typischen Kostentreiber der Zerspanung ab:

  DIM.CHAIN        Geschlossene Maßkette: Teilmaße summieren sich exakt zum
                   Gesamtmaß und alle sind toleriert -> Toleranzkonflikt
                   (Überbestimmung, das Maß ist doppelt festgelegt).
  DIM.NO_TOLERANCE Kein einziges Maß trägt eine Einzeltoleranz, obwohl
                   Passungen/Funktionsmaße zu erwarten wären.
  MFG.TIGHT_TOL    Sehr enge Toleranz (IT ≤ 5 bzw. Spanne < 0,01 mm) –
                   starker Kostentreiber, nur bei Funktionsbedarf sinnvoll.
  MFG.DEEP_HOLE    Bohrungstiefe/Durchmesser > 5 – Tiefbohren nötig.
  MFG.SHARP_CORNER "R0" bzw. scharfe Innenecke gefordert – mit Fräser nicht
                   herstellbar (Erodieren nötig).
  SURF.UNREALISTIC Rauheit feiner als das angegebene Verfahren liefern kann
                   (z. B. Ra 0,2 auf einer Gussfläche).
"""
from __future__ import annotations

import re
from itertools import combinations

from ..drawing.dimensions import DimKind, DimValue
from .base import CheckContext

RE_SHARP_CORNER = re.compile(
    r"\bR\s*0(?![.,]\d*[1-9])\b|scharfkantig\s+innen|sharp\s+internal"
    r"|keine\s+radien|no\s+corner\s+radius|ecke\s+scharf", re.IGNORECASE)
RE_RA_VALUE = re.compile(r"\bRa\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
RE_RZ_VALUE = re.compile(r"\bRz\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
# Verfahren mit ihrer praktisch erreichbaren Feinheit (Ra in µm).
PROCESS_RA_LIMIT = {
    "guss": (re.compile(r"\bguss|casting|\bcast\b|EN[-\s]?GJ|rohteil"
                        r"|unbearbeitet|as[-\s]cast", re.IGNORECASE), 6.3),
    "brennschnitt": (re.compile(r"brennschnitt|autogen|plasmaschnitt"
                                r"|flame[-\s]cut", re.IGNORECASE), 12.5),
    "schmieden": (re.compile(r"geschmiedet|schmiedeteil|forged",
                             re.IGNORECASE), 6.3),
}
# Verfahren, die sehr feine Oberflächen rechtfertigen.
RE_FINE_PROCESS = re.compile(
    r"geschliffen|schleifen|läppen|honen|poliert|ground|lapped|honed"
    r"|polished|superfinish", re.IGNORECASE)


def _axis_groups(dims: list[DimValue], tol: float
                 ) -> list[tuple[str, list[DimValue]]]:
    """Gruppiert Maße zu möglichen Maßketten (gleiche Maßlinie).

    Horizontale Kette: Maßtexte liegen auf gleicher Höhe (y), nebeneinander.
    Vertikale Kette: gleiche Spalte (x), untereinander.
    """
    groups: list[tuple[str, list[DimValue]]] = []
    for axis, key, other in (("h", lambda d: d.bbox.center[1],
                              lambda d: d.bbox.center[0]),
                             ("v", lambda d: d.bbox.center[0],
                              lambda d: d.bbox.center[1])):
        buckets: dict[int, list[DimValue]] = {}
        for d in dims:
            buckets.setdefault(int(key(d) / tol), []).append(d)
        # Nachbarschaftsbuckets zusammenführen (Maßtexte sitzen nicht exakt
        # auf derselben Koordinate).
        merged: dict[int, list[DimValue]] = {}
        for b, items in sorted(buckets.items()):
            target = merged.get(b - 1)
            if target is not None:
                merged[b - 1] = target + items
            else:
                merged[b] = list(items)
        for items in merged.values():
            if len(items) >= 3:
                groups.append((axis, sorted(items, key=other)))
    return groups


def _is_adjacent_chain(parts: list[DimValue], axis: str) -> bool:
    """Teilmaße müssen nebeneinander liegen (keine Überlappung)."""
    spans = []
    for d in parts:
        b = d.bbox
        spans.append((b.x0, b.x1) if axis == "h" else (b.y0, b.y1))
    spans.sort()
    for (_, end), (start, _) in zip(spans, spans[1:]):
        if start < end - 1.0:      # deutliche Überlappung -> keine Kette
            return False
    return True


def check_dimension_chain(ctx: CheckContext, dims: list[DimValue]) -> None:
    """Geschlossene, durchtolerierte Maßkette erkennen.

    Eine echte Kette erfüllt drei Bedingungen gleichzeitig:
      1. die Teilmaße liegen auf EINER Maßlinie und nebeneinander,
      2. ihre Summe ergibt ein weiteres Maß derselben Richtung,
      3. Gesamtmaß und mehrere Teilmaße sind toleriert.
    Ohne die räumliche Prüfung liefert die reine Zahlensuche auf
    maßreichen Zeichnungen Zufallstreffer.
    """
    if not ctx.profile.enabled("DIM.CHAIN"):
        return
    linear = [d for d in dims if d.kind is DimKind.LINEAR and d.value >= 5]
    if len(linear) < 4:
        return
    eps = float(ctx.profile.params.get("chain_epsilon", 0.05))
    line_tol = float(ctx.profile.params.get("chain_line_tol", 8.0))
    reported = 0

    for axis, group in _axis_groups(linear, line_tol):
        toler = [d for d in group if d.tolerance_span]
        if len(toler) < 2:
            continue
        # Kandidaten für das Gesamtmaß: toleriert und größer als der Rest
        for total in sorted(toler, key=lambda d: -d.value):
            parts_pool = [d for d in group
                          if d is not total and d.value < total.value]
            if len(parts_pool) < 2:
                continue
            found = None
            for n in (2, 3, 4):
                if n > len(parts_pool):
                    break
                for combo in combinations(parts_pool, n):
                    if abs(sum(d.value for d in combo) - total.value) > eps:
                        continue
                    if sum(1 for d in combo if d.tolerance_span) < 1:
                        continue
                    if not _is_adjacent_chain(list(combo), axis):
                        continue
                    found = combo
                    break
                if found:
                    break
            if not found:
                continue
            chain = " + ".join(f"{d.value:g}" for d in found)
            ctx.add("DIM.CHAIN",
                    f"Geschlossene Maßkette mit Toleranzkonflikt: "
                    f"{chain} = {total.value:g}, Teil- und Gesamtmaß toleriert",
                    bbox=total.bbox, page=total.page,
                    detail="Bei geschlossenen Ketten summieren sich die "
                           "Einzeltoleranzen; ein Maß muss als Hilfsmaß "
                           "(eingeklammert) oder ohne Toleranz ausgeführt "
                           "werden (ISO 129-1, DIN 406-11).")
            reported += 1
            if reported >= 2:
                return
            break


def check_tight_tolerances(ctx: CheckContext, dims: list[DimValue]) -> None:
    """Sehr enge Toleranzen als Kostentreiber melden."""
    if not ctx.profile.enabled("MFG.TIGHT_TOL"):
        return
    limit_mm = float(ctx.profile.params.get("tight_tol_mm", 0.01))
    limit_it = int(ctx.profile.params.get("tight_tol_it", 5))
    tight = []
    for d in dims:
        span = d.tolerance_span
        grade = d.it_grade
        if (span is not None and span < limit_mm) or (
                grade is not None and grade <= limit_it):
            tight.append(d)
    if not tight:
        return
    max_report = int(ctx.profile.params.get("max_tight_tol_markers", 5))
    for d in tight[:max_report]:
        span = d.tolerance_span
        grade_txt = f" (IT{d.it_grade})" if d.it_grade else ""
        span_txt = f"{span * 1000:.0f} µm" if span else "sehr eng"
        ctx.add("MFG.TIGHT_TOL",
                f"Sehr enge Toleranz: {d.raw} → {span_txt}{grade_txt}",
                bbox=d.bbox, page=d.page,
                detail="Enge Toleranzen sind der stärkste Kostentreiber in "
                       "der Zerspanung (Sonderwerkzeuge, Messmittel, "
                       "Ausschussrisiko). Nur an funktionsrelevanten Maßen "
                       "vorsehen.")
    if len(tight) > max_report:
        ctx.add("MFG.TIGHT_TOL",
                f"… und {len(tight) - max_report} weitere sehr enge Toleranzen",
                detail="Nur die ersten Fundstellen sind im Bild markiert.")


def check_deep_holes(ctx: CheckContext, dims: list[DimValue]) -> None:
    """Tiefe Bohrungen (Tiefe/Durchmesser > Schwelle)."""
    if not ctx.profile.enabled("MFG.DEEP_HOLE"):
        return
    ratio_limit = float(ctx.profile.params.get("deep_hole_ratio", 5.0))
    for d in dims:
        if d.kind not in (DimKind.DIAMETER, DimKind.THREAD) or not d.depth:
            continue
        if d.value <= 0:
            continue
        ratio = d.depth / d.value
        if ratio > ratio_limit:
            ctx.add("MFG.DEEP_HOLE",
                    f"Tiefe Bohrung: ⌀{d.value:g} × {d.depth:g} mm tief "
                    f"(Verhältnis {ratio:.1f}:1)",
                    bbox=d.bbox, page=d.page,
                    detail="Ab etwa 5:1 sind Tiefbohrwerkzeuge, "
                           "Spanbruchstrategien und ggf. Innenkühlung nötig – "
                           "Kosten und Lieferzeit steigen deutlich.")


def check_sharp_corners(ctx: CheckContext) -> None:
    """Scharfe Innenecken bzw. R0 gefordert."""
    if not ctx.profile.enabled("MFG.SHARP_CORNER"):
        return
    for b in ctx.pdf.blocks():
        m = RE_SHARP_CORNER.search(b.text)
        if m:
            ctx.add("MFG.SHARP_CORNER",
                    f"Scharfe Innenecke gefordert („{m.group(0)}“)",
                    bbox=b.bbox, page=b.page,
                    detail="Fräser erzeugen immer einen Eckenradius. Scharfe "
                           "Innenecken erfordern Erodieren oder Räumen – "
                           "Eckenradius zulassen, wenn funktional möglich.")
            return


def check_surface_plausibility(ctx: CheckContext) -> None:
    """Rauheitsangabe feiner, als das genannte Verfahren liefern kann."""
    if not ctx.profile.enabled("SURF.UNREALISTIC"):
        return
    text = ctx.pdf.full_text()
    if RE_FINE_PROCESS.search(text):
        return  # Feinbearbeitung ist angegeben -> plausibel
    ra_values = [float(v.replace(",", ".")) for v in RE_RA_VALUE.findall(text)]
    if not ra_values:
        return
    finest = min(ra_values)
    for name, (regex, limit) in PROCESS_RA_LIMIT.items():
        m = regex.search(text)
        if m and finest < limit / 4:
            ctx.add("SURF.UNREALISTIC",
                    f"Rauheit Ra {finest:g} µm bei Verfahren „{m.group(0)}“ "
                    f"nicht erreichbar",
                    detail=f"Ohne Nachbearbeitung liefert dieses Verfahren "
                           f"etwa Ra {limit} µm. Entweder Feinbearbeitung "
                           f"(Schleifen/Honen) vorgeben oder die "
                           f"Rauheitsforderung anpassen.")
            return
    # Sehr feine Rauheit ohne jedes Feinbearbeitungsverfahren
    fine_limit = float(ctx.profile.params.get("fine_ra_limit", 0.4))
    if finest < fine_limit:
        ctx.add("SURF.UNREALISTIC",
                f"Sehr feine Rauheit Ra {finest:g} µm ohne Angabe eines "
                f"Feinbearbeitungsverfahrens",
                severity=ctx.profile.severity("SURF.UNREALISTIC_MINOR"),
                detail="Ra < 0,4 µm erfordert Schleifen, Honen oder Läppen – "
                       "Verfahren angeben, sonst kalkuliert der Lieferant "
                       "auf Verdacht.")


def run_dimension_checks(ctx: CheckContext, dims: list[DimValue]) -> None:
    check_dimension_chain(ctx, dims)
    check_tight_tolerances(ctx, dims)
    check_deep_holes(ctx, dims)
    check_sharp_corners(ctx)
    check_surface_plausibility(ctx)
