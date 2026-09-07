"""Pruefungen an Bemassung und GPS: Masse, Toleranzen, Form und Lage.

Beides haengt so eng zusammen, dass eine Trennung nur Importe erzeugt
haette: eine Positionstoleranz ohne theoretisch genaues Mass ist ein
Bemassungsfehler und ein GPS-Fehler zugleich.
"""
from __future__ import annotations

# ======================================================================
# dimension_checks
# ======================================================================
# Bemaßungs- und Fertigungsprüfungen.
#
# Deckt die klassischen Bemaßungsfehler (ISO 129-1 / DIN 406) und die
# typischen Kostentreiber der Zerspanung ab:
#
#   DIM.CHAIN        Geschlossene Maßkette: Teilmaße summieren sich exakt zum
#                    Gesamtmaß und alle sind toleriert -> Toleranzkonflikt
#                    (Überbestimmung, das Maß ist doppelt festgelegt).
#   DIM.NO_TOLERANCE Kein einziges Maß trägt eine Einzeltoleranz, obwohl
#                    Passungen/Funktionsmaße zu erwarten wären.
#   MFG.TIGHT_TOL    Sehr enge Toleranz (IT ≤ 5 bzw. Spanne < 0,01 mm) –
#                    starker Kostentreiber, nur bei Funktionsbedarf sinnvoll.
#   MFG.DEEP_HOLE    Bohrungstiefe/Durchmesser > 5 – Tiefbohren nötig.
#   MFG.SHARP_CORNER "R0" bzw. scharfe Innenecke gefordert – mit Fräser nicht
#                    herstellbar (Erodieren nötig).
#   SURF.UNREALISTIC Rauheit feiner als das angegebene Verfahren liefern kann
#                    (z. B. Ra 0,2 auf einer Gussfläche).
#   SURF.TOL_MISMATCH Rauheit zu grob für die geforderte Toleranz – eine
#                    H7-Passung lässt sich mit Rz 63 nicht einhalten, weil
#                    das Rauheitsprofil selbst schon die halbe Toleranz
#                    verbraucht.
#   DIM.TOL_ORDER    Grenzabmaße vertauscht (oberes Abmaß kleiner als das
#                    untere) – das Maß ist so nicht fertigbar.
#   DIM.BASIC_TOL    Theoretisch genaues Maß (eingerahmt) zusätzlich
#                    toleriert – Widerspruch nach ISO 1101.
#   THRD.DEPTH       Gewinde tiefer gefordert als die Bohrung – so nicht
#                    herstellbar (der Bohrer kommt nicht weiter).
#   THRD.SHORT       Einschraubtiefe unter 1×D – die Verbindung trägt die
#                    Schraubenfestigkeit nicht.



import re
from itertools import combinations

from .zeichnung import DimKind, DimValue
from .regeln import CheckContext

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


def check_tolerance_order(ctx: CheckContext, dims: list[DimValue]) -> None:
    """Vertauschte Grenzabmaße und tolerierte TED-Maße melden."""
    for d in dims:
        if (ctx.profile.enabled("DIM.TOL_ORDER")
                and d.tol_plus is not None and d.tol_minus is not None
                and d.tol_plus < d.tol_minus):
            ctx.add("DIM.TOL_ORDER",
                    f"Grenzabmaße vertauscht bei „{d.raw}“: oberes Abmaß "
                    f"{d.tol_plus:+g} liegt unter dem unteren "
                    f"{d.tol_minus:+g}",
                    bbox=d.bbox, page=d.page,
                    detail="So beschrieben ist das Toleranzfeld leer – das "
                           "Maß kann nicht gefertigt werden. Nach ISO 129-1 "
                           "steht das obere Abmaß oben bzw. zuerst.")
        if (ctx.profile.enabled("DIM.BASIC_TOL") and d.is_basic
                and (d.tol_plus is not None or d.tol_minus is not None
                     or d.fit)):
            ctx.add("DIM.BASIC_TOL",
                    f"Theoretisch genaues Maß „{d.raw}“ trägt zusätzlich "
                    f"eine Toleranz",
                    bbox=d.bbox, page=d.page,
                    detail="Ein eingerahmtes Maß (TED) ist per Definition "
                           "toleranzfrei; die Abweichung regelt allein die "
                           "zugehörige Lagetoleranz (ISO 1101). Entweder den "
                           "Rahmen entfernen oder die Toleranz streichen.")


def check_roughness_vs_tolerance(ctx: CheckContext,
                                 dims: list[DimValue]) -> None:
    """Rauheit gegen die engste Maßtoleranz prüfen.

    Praxisregel: Das Rauheitsprofil darf die Maßtoleranz nicht aufzehren.
    Üblich ist Rz ≤ 1/4 der Toleranzbreite; gemeldet wird erst ab der
    Hälfte, damit nur eindeutige Widersprüche auffallen.
    """
    if not ctx.profile.enabled("SURF.TOL_MISMATCH"):
        return
    coarsest = _coarsest_roughness_um(ctx)
    if coarsest is None:
        return
    tightest = None
    for d in dims:
        span = d.tolerance_span
        if span and (tightest is None or span < tightest[0]):
            tightest = (span, d)
    if tightest is None:
        return
    span_mm, dim = tightest
    span_um = span_mm * 1000.0
    ratio = float(ctx.profile.rule_param("SURF.TOL_MISMATCH", "max_ratio", 0.5))
    if coarsest <= span_um * ratio:
        return
    ctx.add("SURF.TOL_MISMATCH",
            f"Rauheit Rz {coarsest:g} µm ist zu grob für die Toleranz von "
            f"„{dim.raw}“ ({span_um:.0f} µm)",
            bbox=dim.bbox, page=dim.page,
            detail=f"Das Rauheitsprofil verbraucht "
                   f"{coarsest / span_um * 100:.0f} % der Toleranzbreite; "
                   f"üblich sind höchstens 25 %. Entweder eine feinere "
                   f"Oberfläche fordern (Rz ≤ {span_um / 4:.1f} µm) oder die "
                   f"Toleranz aufweiten. Sonst ist das Maß nicht "
                   f"reproduzierbar messbar.")


def _coarsest_roughness_um(ctx: CheckContext) -> float | None:
    """Gröbste Rauheitsangabe der Zeichnung als Rz in µm.

    Ra-Angaben werden mit dem in der Praxis üblichen Faktor 4 auf Rz
    umgerechnet (Rz ≈ 4 × Ra für spanend erzeugte Oberflächen).
    """
    text = ctx.pdf.full_text()
    values: list[float] = []
    for m in RE_RZ_VALUE.finditer(text):
        values.append(_num(m.group(1)))
    for m in RE_RA_VALUE.finditer(text):
        values.append(_num(m.group(1)) * 4.0)
    values = [v for v in values if 0 < v <= 200]
    return max(values) if values else None


def _num(raw: str) -> float:
    return float(raw.replace(",", "."))


# Mindest-Einschraubtiefe als Vielfaches des Nenndurchmessers. Faustwerte
# der Verbindungstechnik (VDI 2230): Stahl 1×D, Guss 1,25×D, Alu 1,5–2×D.
MIN_ENGAGEMENT = {"stahl": 1.0, "guss": 1.25, "alu": 1.5}
RE_SOFT_MATERIAL = re.compile(
    r"\bAl(?:Mg|Si|Cu|Zn)|EN\s?AW|aluminium|\bGD-?Al|kunststoff|\bPA6|POM",
    re.IGNORECASE)


def check_thread_depths(ctx: CheckContext, dims: list[DimValue]) -> None:
    """Gewindetiefe gegen Bohrtiefe und gegen die Mindesteinschraubtiefe.

    Beide Fälle stehen auf der Zeichnung, werden aber selten gegengerechnet:
    „M10 ↧25" mit „⌀8,5 ↧20" ist nicht herstellbar, und „M10 ↧6" trägt in
    Aluminium nicht.
    """
    threads = [d for d in dims if d.kind is DimKind.THREAD and d.depth]
    if not threads:
        return
    weich = bool(RE_SOFT_MATERIAL.search(ctx.pdf.full_text()))
    faktor = MIN_ENGAGEMENT["alu"] if weich else MIN_ENGAGEMENT["stahl"]
    bohrungen = [d for d in dims if d.kind is DimKind.DIAMETER and d.depth]

    for t in threads:
        if ctx.profile.enabled("THRD.DEPTH"):
            core = _core_hole(t.value)
            passende = [b for b in bohrungen
                        if core and abs(b.value - core) <= 0.6]
            for b in passende:
                if t.depth > b.depth + 0.5:
                    ctx.add("THRD.DEPTH",
                            f"Gewinde „{t.raw}“ ist {t.depth:g} mm tief "
                            f"gefordert, die Bohrung ⌀{b.value:g} nur "
                            f"{b.depth:g} mm",
                            bbox=t.bbox, page=t.page,
                            detail="Das Gewinde kann nicht tiefer sein als "
                                   "die Kernbohrung. Üblich sind 2–5 mm "
                                   "Bohrungsüberlauf für den Gewindeauslauf "
                                   "(bei Grundlöchern zwingend).")
                    break
        if ctx.profile.enabled("THRD.SHORT") and t.depth < t.value * faktor:
            werkstoff = "weichem Werkstoff (Alu/Kunststoff)" if weich else "Stahl"
            ctx.add("THRD.SHORT",
                    f"Einschraubtiefe {t.depth:g} mm bei „{t.raw}“ ist kurz – "
                    f"in {werkstoff} sind mindestens "
                    f"{t.value * faktor:.0f} mm üblich",
                    bbox=t.bbox, page=t.page,
                    detail="Unter etwa 1×D (Stahl) bzw. 1,5×D (Aluminium) "
                           "reißt das Gewinde aus, bevor die Schraube ihre "
                           "Festigkeit erreicht (VDI 2230). Entweder tiefer "
                           "gewinden oder Gewindeeinsatz vorsehen.")


def _core_hole(nominal: float) -> float | None:
    from .pruef_geometrie import THREAD_CORE_DIA

    return THREAD_CORE_DIA.get(int(nominal))


def run_dimension_checks(ctx: CheckContext, dims: list[DimValue]) -> None:
    check_dimension_chain(ctx, dims)
    check_tight_tolerances(ctx, dims)
    check_deep_holes(ctx, dims)
    check_sharp_corners(ctx)
    check_surface_plausibility(ctx)
    check_tolerance_order(ctx, dims)
    check_roughness_vs_tolerance(ctx, dims)
    check_thread_depths(ctx, dims)


# ======================================================================
# gps_checks
# ======================================================================
# GPS-Tiefenprüfung: Bezugssystem, Hüllbedingung, theoretisch genaue Maße.
#
# Deckt die in der Praxis teuersten Tolerierungsfehler ab (Quellen: DGQ zu
# ISO-GPS-Tolerierungsgrundsätzen, GD&T-Reviewpraxis):
#
#   GPS.ENVELOPE        Passung (z. B. ⌀20 H7) ohne Hüllbedingung Ⓔ und ohne
#                       Formtoleranz. Nach ISO 8015 gilt das Unabhängigkeits-
#                       prinzip: die Toleranz begrenzt nur das lokale
#                       Zweipunktmaß – das Teil darf krumm/unrund sein.
#   GPS.DATUM_UNDEFINED Toleranzrahmen verweist auf Bezug A/B/C, der nirgends
#                       als Bezugsstelle definiert ist.
#   GPS.DATUM_UNUSED    Bezug definiert, aber in keinem Toleranzrahmen benutzt.
#   GPS.POSITION_NO_TED Positionstoleranz ohne theoretisch genaue Maße (TED):
#                       der Sollort ist damit nicht festgelegt.
#   GPS.MOD_ON_FORM     Materialbedingung Ⓜ/Ⓛ an einer Formtoleranz – nur bei
#                       Größenmaßen zulässig.



import re

from .zeichnung import DimKind, DimValue
from .zeichnung import find_feature_frames
from .regeln import CheckContext

# Symbolgruppen (Unicode-GD&T)
SYM_POSITION = "⌖"
SYM_FORM = "⏤⏥○⌭⌒"
SYM_ORIENTATION = "∥⊥∠"
SYM_RUNOUT = "↗⌰"
SYM_PROFILE = "⌓⌔"
SYM_LOCATION = SYM_POSITION + "◎⌯"
SYM_NEEDS_DATUM = SYM_POSITION + SYM_ORIENTATION + SYM_RUNOUT + "◎⌯"
SYM_ALL = SYM_FORM + SYM_NEEDS_DATUM + SYM_PROFILE

# Hüllbedingung Ⓔ (U+24BA) bzw. als "(E)" geschriebene Ersatzform.
RE_ENVELOPE = re.compile(r"Ⓔ|\(\s*E\s*\)|ISO\s*14405[-\s]?1?.{0,20}?Ⓔ")
# Bezugsstellen-Definition: Buchstabe im Bezugsdreieck; im Textlayer meist
# als alleinstehender Großbuchstabe bei "Bezug"/"Datum" oder im Rahmen.
RE_DATUM_DEF = re.compile(
    r"(?:bezug|bezüge|datum|datums)\s*:?\s*([A-Z](?:\s*[,/-]\s*[A-Z])*)",
    re.IGNORECASE)
# Bezüge in einem Toleranzrahmen: Symbol, Wert, dann 1-3 Bezugsbuchstaben.
# Nur auf DERSELBEN Zeile ([ \t] statt \s) und als isolierte Großbuchstaben –
# sonst greift der Regex in Folgewörter ("Bezug" -> B).
RE_FCF_DATUMS = re.compile(
    rf"[{SYM_NEEDS_DATUM}][ \t]*⌀?[ \t]*\d+(?:[.,]\d+)?[ \t]*[ⓂⓁ]?"
    r"((?:[ \t]*[-–|]?[ \t]*\b[A-Z]\b(?![a-zäöüß])"
    r"(?:[ \t]*[ⓂⓁ])?){1,3})")
RE_MODIFIER_ON_FORM = re.compile(
    rf"[{SYM_FORM}]\s*⌀?\s*\d+(?:[.,]\d+)?\s*[ⓂⓁ]")
# Formtoleranz an einem Größenmaß (Rundheit/Zylindrizität) – hebt den
# Hüllbedingungs-Hinweis auf, weil die Form dann geregelt ist.
RE_FORM_TOL = re.compile(rf"[{SYM_FORM}]\s*⌀?\s*\d+(?:[.,]\d+)?")


def _blocks_text(ctx: CheckContext) -> str:
    return ctx.pdf.full_text()


def _find_block(ctx: CheckContext, regex: re.Pattern):
    for b in ctx.pdf.blocks():
        m = regex.search(b.text)
        if m:
            return m, b.bbox, b.page
    return None


def check_envelope_requirement(ctx: CheckContext,
                               dims: list[DimValue]) -> None:
    """Passungen ohne Hüllbedingung und ohne Formtoleranz."""
    if not ctx.profile.enabled("GPS.ENVELOPE"):
        return
    text = _blocks_text(ctx)
    # Nur relevant, wenn das Unabhängigkeitsprinzip gilt (ISO 8015 /
    # ISO 14405 bzw. keine gegenteilige Angabe) – das ist der Normalfall.
    if RE_ENVELOPE.search(text):
        return
    if RE_FORM_TOL.search(text):
        return  # Form ist über eine Formtoleranz geregelt
    # Enge Passungen (IT ≤ 8) an Größenmaßen sind die kritischen Fälle.
    critical = [d for d in dims
                if d.fit and (d.it_grade or 99) <= 8
                and d.kind in (DimKind.DIAMETER, DimKind.LINEAR)]
    if not critical:
        return
    example = critical[0]
    names = ", ".join(sorted({f"⌀{d.value:g} {d.fit}" for d in critical})[:4])
    ctx.add("GPS.ENVELOPE",
            f"Enge Passung ohne Hüllbedingung Ⓔ und ohne Formtoleranz "
            f"({names})",
            bbox=example.bbox, page=example.page,
            detail="Nach ISO 8015 (Unabhängigkeitsprinzip) begrenzt die "
                   "Passungstoleranz nur das lokale Zweipunktmaß – Form "
                   "(Rundheit, Geradheit) bleibt unbegrenzt. Für Fügeflächen "
                   "Ⓔ ergänzen oder Formtoleranz angeben.")


def check_datum_consistency(ctx: CheckContext) -> None:
    """Bezüge in Toleranzrahmen vs. definierte Bezugsstellen.

    Ein Bezug gilt als definiert, wenn sein Buchstabe AUSSERHALB der
    Toleranzrahmen vorkommt (Bezugsdreieck, "Bezug A = …"). Kommt er nur
    innerhalb von Toleranzrahmen vor, fehlt die Bezugsstelle (ISO 5459).
    """
    text = _blocks_text(ctx)
    referenced: dict[str, int] = {}
    for m in RE_FCF_DATUMS.finditer(text):
        for letter in re.findall(r"[A-Z]", m.group(1)):
            referenced[letter] = referenced.get(letter, 0) + 1
    # Zusätzlich die grafisch erkannten Toleranzrahmen auswerten – auf
    # realen CAD-Zeichnungen liegt GD&T meist als Vektorgrafik vor.
    for frame in ctx.feature_frames:
        for letter in frame.datums:
            referenced[letter] = referenced.get(letter, 0) + 1
    if not referenced:
        return

    # Vorkommen je Buchstabe als eigenständiges Wort im gesamten Text.
    standalone: dict[str, int] = {}
    for w in ctx.pdf.words():
        t = w.text.strip().strip("[]()")
        if len(t) == 1 and t.isalpha() and t.isupper():
            standalone[t] = standalone.get(t, 0) + 1
    # Explizite Definitionen ("Bezug A", "datum A-B") zählen extra.
    explicit: set[str] = set()
    for m in RE_DATUM_DEF.finditer(text):
        explicit.update(re.findall(r"[A-Z]", m.group(1)))

    if ctx.profile.enabled("GPS.DATUM_UNDEFINED"):
        missing = sorted(
            letter for letter, n_ref in referenced.items()
            if letter not in explicit and standalone.get(letter, 0) <= n_ref)
        if missing:
            hit = _find_block(ctx, RE_FCF_DATUMS)
            bbox, page = (hit[1], hit[2]) if hit else (None, 0)
            ctx.add("GPS.DATUM_UNDEFINED",
                    f"Toleranzrahmen verweist auf nicht definierte Bezüge: "
                    f"{', '.join(missing)}",
                    bbox=bbox, page=page,
                    detail="Der Bezugsbuchstabe kommt nur im Toleranzrahmen "
                           "vor – ohne Bezugsstelle am Formelement ist das "
                           "Bezugssystem unvollständig und die Lage nicht "
                           "prüfbar (ISO 5459).")
    if ctx.profile.enabled("GPS.DATUM_UNUSED"):
        unused = sorted(d for d in explicit - set(referenced) if d in "ABCDEFG")
        if unused and len(unused) <= 3:
            ctx.add("GPS.DATUM_UNUSED",
                    f"Bezug {', '.join(unused)} definiert, aber in keinem "
                    f"Toleranzrahmen verwendet",
                    detail="Entweder fehlt eine Lagetoleranz oder der Bezug "
                           "ist überflüssig – bitte klären.")


def check_position_needs_ted(ctx: CheckContext, dims: list[DimValue]) -> None:
    """Positionstoleranz ohne theoretisch genaue Maße."""
    if not ctx.profile.enabled("GPS.POSITION_NO_TED"):
        return
    text = _blocks_text(ctx)
    if SYM_POSITION not in text:
        return
    if any(d.is_basic for d in dims):
        return
    hit = _find_block(ctx, re.compile(re.escape(SYM_POSITION)))
    bbox, page = (hit[1], hit[2]) if hit else (None, 0)
    ctx.add("GPS.POSITION_NO_TED",
            "Positionstoleranz ⌖ verwendet, aber keine theoretisch genauen "
            "Maße (eingerahmt) erkennbar",
            bbox=bbox, page=page,
            detail="Der Sollort muss mit TED (eingerahmten Maßen) festgelegt "
                   "sein; tolerierte Maße dürfen dafür nicht verwendet werden "
                   "(ISO 1101/5458). Hinweis: eingerahmte Maße sind im "
                   "PDF-Textlayer nicht immer erkennbar – bitte sichtprüfen.")


def check_modifier_placement(ctx: CheckContext) -> None:
    """Materialbedingung Ⓜ/Ⓛ an einer Formtoleranz."""
    if not ctx.profile.enabled("GPS.MOD_ON_FORM"):
        return
    hit = _find_block(ctx, RE_MODIFIER_ON_FORM)
    if hit:
        m, bbox, page = hit
        ctx.add("GPS.MOD_ON_FORM",
                f"Materialbedingung an einer Formtoleranz („{m.group(0)}“)",
                bbox=bbox, page=page,
                detail="Ⓜ/Ⓛ sind nur bei Größenmaßen (Bohrung, Welle) "
                       "zulässig, nicht bei Ebenheit/Geradheit/Rundheit "
                       "(ISO 2692).")


def check_diameter_zone_needs_datum(ctx: CheckContext) -> None:
    """⌀-Toleranzzone ohne Bezug.

    Eine kreis-/zylinderförmige Toleranzzone gibt es nur bei Lage- und
    Positionstoleranzen – und die brauchen zwingend ein Bezugssystem
    (ISO 1101/5459). Formtoleranzen haben nie eine ⌀-Zone.
    """
    if not ctx.profile.enabled("GPS.ZONE_NO_DATUM"):
        return
    for frame in ctx.feature_frames:
        if frame.diameter_zone and not frame.has_datums:
            ctx.add("GPS.ZONE_NO_DATUM",
                    f"Toleranzrahmen mit ⌀-Toleranzzone (⌀{frame.value:g}) "
                    f"ohne Bezug",
                    bbox=frame.bbox, page=frame.page,
                    detail="Kreisförmige Toleranzzonen kommen nur bei Lage-/"
                           "Positionstoleranzen vor; ohne Bezugssystem ist die "
                           "Lage nicht definiert (ISO 1101).")
            return


def check_gdt_readability(ctx: CheckContext) -> None:
    """Toleranzrahmen als Grafik: Symbolart nicht maschinell prüfbar."""
    if not ctx.profile.enabled("DOC.GDT_GRAPHIC"):
        return
    graphic = [f for f in ctx.feature_frames if not f.symbol]
    if not graphic:
        return
    text_symbols = any(c in ctx.pdf.full_text() for c in SYM_ALL)
    if text_symbols:
        return
    ctx.add("DOC.GDT_GRAPHIC",
            f"{len(graphic)} Toleranzrahmen erkannt, deren GD&T-Symbol nur "
            f"als Grafik vorliegt",
            bbox=graphic[0].bbox, page=graphic[0].page,
            detail="Toleranzwerte und Bezüge werden geprüft, die Art der "
                   "Toleranz (Position, Ebenheit, Rundlauf …) jedoch nicht – "
                   "diese Angaben bitte visuell prüfen.")


def run_gps_checks(ctx: CheckContext, dims: list[DimValue]) -> None:
    check_envelope_requirement(ctx, dims)
    check_datum_consistency(ctx)
    check_position_needs_ted(ctx, dims)
    check_modifier_placement(ctx)
    check_diameter_zone_needs_datum(ctx)
    check_gdt_readability(ctx)
