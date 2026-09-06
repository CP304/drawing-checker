"""Verfahrensspezifische Vollständigkeitsprüfungen.

Prüft je erkanntem Fertigungsverfahren, ob die dafür zwingenden Angaben auf
der Zeichnung stehen. Grundlage: Fertigungs- und Schweißpraxis (ISO 2553,
ISO 9692, VDG-Merkblatt K 200, Blech-Konstruktionsrichtlinien).

  WELD.NO_SIZE      Schweißsymbolik ohne Nahtdicke (a-/z-Maß)
  WELD.AZ_MIXED     a- und z-Maße gemischt – teuerster Lesefehler der Praxis
  WELD.NO_PREP      Stumpfnaht ohne Angabe der Nahtvorbereitung (ISO 9692)
  CAST.NO_DRAFT     Gussteil ohne Formschrägen-Angabe (ISO 10135/DIN EN 12890)
  CAST.NO_RMA       Gussteil mit Bearbeitung, aber ohne Bearbeitungszugabe
  SHEET.NO_THICK    Blech-/Biegeteil ohne Blechdickenangabe
  SHEET.NO_RADIUS   Abkantung ohne Biegeradius
  HT.NO_HARDNESS    Wärmebehandlung ohne Härtewert (DIN 6773)
  HT.NO_DEPTH       Randschichthärten ohne Einhärtetiefe (Eht/CHD/NHD)
  HT.HARDNESS_LIMIT Härteforderung über dem, was der Werkstoff hergibt
"""
from __future__ import annotations

import re

from ..drawing.dimensions import DimKind, DimValue
from .base import CheckContext

# --- Schweißen ------------------------------------------------------------
# a-Maß (Nahtdicke) und z-Maß (Schenkellänge) einer Kehlnaht.
RE_WELD_A = re.compile(r"(?<![A-Za-z0-9])a\s?(\d{1,2}(?:[.,]\d)?)\b")
RE_WELD_Z = re.compile(r"(?<![A-Za-z0-9])z\s?(\d{1,2}(?:[.,]\d)?)\b")
RE_WELD_CONTEXT = re.compile(
    r"schwei[ßs]|weld|naht|seam|ISO\s*2553|ISO\s*5817|kehlnaht|fillet",
    re.IGNORECASE)
RE_BUTT_WELD = re.compile(
    r"stumpfnaht|stumpfsto[ßs]|\bV-?naht\b|\bY-?naht\b|\bU-?naht\b"
    r"|\bHV-?naht\b|\bDV-?naht\b|butt\s*weld|groove\s*weld|full\s*pen",
    re.IGNORECASE)
RE_WELD_PREP = re.compile(
    r"ISO\s*9692|nahtvorbereitung|fugenform|wurzel(?:öffnung|spalt)"
    r"|öffnungswinkel|steghöhe|joint\s*preparation|root\s*(?:gap|face)",
    re.IGNORECASE)

# --- Guss -----------------------------------------------------------------
RE_CAST_CONTEXT = re.compile(
    r"\bguss(?:teil|rohteil|stück)?\b|casting|EN[-\s]?GJ|rohteil|sandguss"
    r"|druckguss|kokillenguss", re.IGNORECASE)
RE_DRAFT = re.compile(
    r"formschräge|aushebeschräge|draft\s*angle|entformungsschräge"
    r"|ISO\s*10135|DIN\s*EN\s*12890|\b\d{1,2}\s*°\s*(?:formschräge|draft)",
    re.IGNORECASE)
RE_RMA = re.compile(
    r"bearbeitungszugabe|aufma[ßs]|\bRMA\b|machining\s*allowance"
    r"|zugabe\s*\d|ISO\s*8062-?3", re.IGNORECASE)
RE_MACHINED_SURFACE = re.compile(
    r"bearbeitet|gefräst|gedreht|geschliffen|machined|spanend|\bRa\s*\d"
    r"|\bH[789]\b|\bh[6789]\b", re.IGNORECASE)

# --- Blech ----------------------------------------------------------------
RE_SHEET_CONTEXT = re.compile(
    r"\bblech\b|abgekantet|gekantet|abkanten|kantung|biegeteil|sheet\s*metal"
    r"|laserzuschnitt|lasergeschnitten|\bbend(?:ing)?\b|abwicklung",
    re.IGNORECASE)
RE_SHEET_THICK = re.compile(
    r"blechdicke|blechstärke|materialstärke|\bdicke\s*\d|\bt\s*=\s*\d"
    r"|sheet\s*thickness|thickness\s*\d|\bs\s*=\s*\d", re.IGNORECASE)
RE_BEND_RADIUS = re.compile(
    r"biegeradius|innenradius|\bri\s*=|bend\s*radius|inner\s*radius"
    r"|biegeradien", re.IGNORECASE)
RE_BEND_PRESENT = re.compile(
    r"abgekantet|gekantet|abkanten|kantung|biegeteil|biegewinkel"
    r"|\bbend(?:ing|s)?\b|abwicklung", re.IGNORECASE)


def _find(ctx: CheckContext, regex: re.Pattern):
    for b in ctx.pdf.blocks():
        m = regex.search(b.text)
        if m:
            return m, b.bbox, b.page
    return None


def check_weld_details(ctx: CheckContext) -> None:
    hit = _find(ctx, RE_WELD_CONTEXT)
    if not hit:
        return
    _m, bbox, page = hit
    text = ctx.pdf.full_text()
    a_sizes = RE_WELD_A.findall(text)
    z_sizes = RE_WELD_Z.findall(text)

    if ctx.profile.enabled("WELD.NO_SIZE") and not a_sizes and not z_sizes:
        ctx.add("WELD.NO_SIZE",
                "Schweißangaben ohne Nahtdicke (a-Maß bzw. z-Maß)",
                bbox=bbox, page=page,
                detail="Ohne Nahtdicke ist die Verbindung nicht bemessen – "
                       "a (Nahtdicke) oder z (Schenkellänge) nach ISO 2553 "
                       "angeben.")
    elif ctx.profile.enabled("WELD.AZ_MIXED") and a_sizes and z_sizes:
        ctx.add("WELD.AZ_MIXED",
                f"a- und z-Maße gemischt verwendet (a: {', '.join(a_sizes[:3])}"
                f" / z: {', '.join(z_sizes[:3])})",
                bbox=bbox, page=page,
                detail="a-Maß (Nahtdicke) und z-Maß (Schenkellänge) "
                       "unterscheiden sich um Faktor √2 (~29 %). Gemischte "
                       "Angaben auf einer Zeichnung führen regelmäßig zu "
                       "unterdimensionierten Nähten – einheitlich bemaßen.")

    if ctx.profile.enabled("WELD.NO_PREP"):
        butt = _find(ctx, RE_BUTT_WELD)
        if butt and not _find(ctx, RE_WELD_PREP):
            _bm, bbbox, bpage = butt
            ctx.add("WELD.NO_PREP",
                    "Stumpf-/Fugennaht ohne Angabe der Nahtvorbereitung",
                    bbox=bbbox, page=bpage,
                    detail="Fugenform, Öffnungswinkel und Wurzelspalt nach "
                           "ISO 9692 angeben – sonst entscheidet der "
                           "Lieferant über die Nahtqualität.")


def check_cast_details(ctx: CheckContext) -> None:
    hit = _find(ctx, RE_CAST_CONTEXT)
    if not hit:
        return
    _m, bbox, page = hit
    if ctx.profile.enabled("CAST.NO_DRAFT") and not _find(ctx, RE_DRAFT):
        ctx.add("CAST.NO_DRAFT",
                "Gussteil ohne Angabe von Formschrägen",
                bbox=bbox, page=page,
                detail="Formschrägen sind in Winkelgraden anzugeben "
                       "(DIN EN 12890 / ISO 10135); ohne Angabe legt sie die "
                       "Gießerei fest – mit Folgen für Maße und Gewicht.")
    if (ctx.profile.enabled("CAST.NO_RMA")
            and _find(ctx, RE_MACHINED_SURFACE) and not _find(ctx, RE_RMA)):
        ctx.add("CAST.NO_RMA",
                "Gussteil mit bearbeiteten Flächen, aber ohne "
                "Bearbeitungszugabe (RMA)",
                bbox=bbox, page=page,
                detail="Bearbeitungszugabe nach ISO 8062-3 angeben, sonst ist "
                       "unklar, ob das Rohteil genug Material für die "
                       "Bearbeitung hat.")


def check_sheet_details(ctx: CheckContext, dims: list[DimValue]) -> None:
    hit = _find(ctx, RE_SHEET_CONTEXT)
    if not hit:
        return
    _m, bbox, page = hit
    if ctx.profile.enabled("SHEET.NO_THICK") and not _find(ctx, RE_SHEET_THICK):
        ctx.add("SHEET.NO_THICK",
                "Blech-/Biegeteil ohne ausgewiesene Blechdicke",
                bbox=bbox, page=page,
                detail="Blechdicke explizit angeben (z. B. „Blechdicke 3 mm“ "
                       "oder t = 3) – aus der Ansicht allein ist sie für den "
                       "Zuschnitt nicht eindeutig.")
    if ctx.profile.enabled("SHEET.NO_RADIUS"):
        bend = _find(ctx, RE_BEND_PRESENT)
        has_radius = bool(_find(ctx, RE_BEND_RADIUS)
                          or [d for d in dims if d.kind is DimKind.RADIUS])
        if bend and not has_radius:
            _bm, bbbox, bpage = bend
            ctx.add("SHEET.NO_RADIUS",
                    "Abkantung ohne Angabe des Biegeradius",
                    bbox=bbbox, page=bpage,
                    detail="Innenradius angeben (Faustregel ri ≥ Blechdicke). "
                           "Ohne Angabe wählt der Fertiger das Werkzeug – "
                           "Abwicklung und Endmaße ändern sich dadurch.")


def run_process_checks(ctx: CheckContext, dims: list[DimValue]) -> None:
    check_weld_details(ctx)
    check_cast_details(ctx)
    check_sheet_details(ctx, dims)
    check_heat_treatment(ctx)


# --- Wärmebehandlung (DIN 6773) -------------------------------------------
RE_HARDNESS_HRC = re.compile(r"(\d{2}(?:[.,]\d)?)\s*[-–+±]?\s*(?:\d{1,2})?\s*HRC",
                             re.IGNORECASE)
RE_HARDNESS_HV = re.compile(r"(\d{3,4})\s*HV\s*\d*", re.IGNORECASE)
RE_HARDNESS_ANY = re.compile(r"\bHRC\b|\bHV\s*\d|\bHB\b|härte(?!n)|hardness",
                             re.IGNORECASE)
RE_CASE_DEPTH = re.compile(
    r"\bEht\b|\bCHD\b|\bNHD\b|\bSHD\b|einhärt(?:e|ungs)tiefe|nitrierhärtetiefe"
    r"|case\s*depth|einsatztiefe|\bRht\b", re.IGNORECASE)
RE_SURFACE_HT = re.compile(
    r"einsatzgehärtet|einsatzhärten|aufgekohlt|carburi[sz]|nitrier|nitrid"
    r"|randschichtgehärtet|induktivgehärtet|induction\s*harden|case\s*harden"
    r"|flammgehärtet", re.IGNORECASE)
# Genormter Lieferzustand im Werkstoffnamen (+QT, +N, +A …): Wärmebehandlung
# und Festigkeit sind damit normativ festgelegt (z. B. EN 10083) – eine
# separate Härteangabe ist dann NICHT erforderlich.
RE_DELIVERY_STATE = re.compile(
    r"\+\s*(?:QT|AT|NT|AR|N|A|C|M|P|SR|U)\b")
RE_STRENGTH = re.compile(
    r"\b\d{3,4}\s*(?:N/mm²|N/mm2|MPa)\b|\bRm\s*[≥>=]|\bRe(?:H|L)?\s*[≥>=]",
    re.IGNORECASE)
RE_HT_PROCESS = re.compile(
    r"gehärtet|härten|vergütet|vergüten|hardened|quenched|tempered"
    r"|einsatzgehärtet|nitriert", re.IGNORECASE)


def check_heat_treatment(ctx: CheckContext) -> None:
    """Härteangaben auf Vollständigkeit und Plausibilität prüfen (DIN 6773)."""
    from .materials import find_materials

    ht = _find(ctx, RE_HT_PROCESS)
    if not ht:
        return
    _m, bbox, page = ht
    text = ctx.pdf.full_text()

    # 1) Härteverfahren ohne Härtewert
    if (ctx.profile.enabled("HT.NO_HARDNESS")
            and not RE_HARDNESS_ANY.search(text)
            and not RE_DELIVERY_STATE.search(text)
            and not RE_STRENGTH.search(text)):
        ctx.add("HT.NO_HARDNESS",
                "Wärmebehandlung angegeben, aber kein Härtewert",
                bbox=bbox, page=page,
                detail="Nach DIN 6773 gehören Oberflächenhärte (HRC/HV) und "
                       "Toleranz zur Angabe – sonst ist das Ergebnis nicht "
                       "prüfbar.")

    # 2) Randschichtverfahren ohne Einhärtetiefe
    surface = _find(ctx, RE_SURFACE_HT)
    if (ctx.profile.enabled("HT.NO_DEPTH") and surface
            and not RE_CASE_DEPTH.search(text)):
        _sm, sbbox, spage = surface
        ctx.add("HT.NO_DEPTH",
                "Randschichthärten ohne Angabe der Einhärtetiefe",
                bbox=sbbox, page=spage,
                detail="Einhärtungstiefe (Eht/CHD bzw. NHD beim Nitrieren) "
                       "mit Grenzhärte angeben – ohne sie ist die Randschicht "
                       "nicht spezifiziert (DIN 6773 / ISO 15787).")

    # 3) Härtewert über dem, was der Werkstoff hergibt
    if not ctx.profile.enabled("HT.HARDNESS_LIMIT"):
        return
    hits = find_materials(ctx)
    material = next((h.material for h in hits if h.material.max_hrc), None)
    if material is None:
        return
    values = [float(v.replace(",", ".")) for v in RE_HARDNESS_HRC.findall(text)]
    if not values:
        return
    reserve = float(ctx.profile.params.get("hardness_reserve_hrc", 2))
    highest = max(values)
    if highest > material.max_hrc + reserve:
        ctx.add("HT.HARDNESS_LIMIT",
                f"Härteforderung {highest:g} HRC über dem für {material.name} "
                f"erreichbaren Wert (ca. {material.max_hrc:g} HRC)",
                bbox=bbox, page=page,
                detail="Entweder ist der Werkstoff für die geforderte Härte "
                       "ungeeignet oder die Härteangabe ist zu hoch – "
                       "Werkstoff oder Anforderung anpassen.")
