"""GPS-Tiefenprüfung: Bezugssystem, Hüllbedingung, theoretisch genaue Maße.

Deckt die in der Praxis teuersten Tolerierungsfehler ab (Quellen: DGQ zu
ISO-GPS-Tolerierungsgrundsätzen, GD&T-Reviewpraxis):

  GPS.ENVELOPE        Passung (z. B. ⌀20 H7) ohne Hüllbedingung Ⓔ und ohne
                      Formtoleranz. Nach ISO 8015 gilt das Unabhängigkeits-
                      prinzip: die Toleranz begrenzt nur das lokale
                      Zweipunktmaß – das Teil darf krumm/unrund sein.
  GPS.DATUM_UNDEFINED Toleranzrahmen verweist auf Bezug A/B/C, der nirgends
                      als Bezugsstelle definiert ist.
  GPS.DATUM_UNUSED    Bezug definiert, aber in keinem Toleranzrahmen benutzt.
  GPS.POSITION_NO_TED Positionstoleranz ohne theoretisch genaue Maße (TED):
                      der Sollort ist damit nicht festgelegt.
  GPS.MOD_ON_FORM     Materialbedingung Ⓜ/Ⓛ an einer Formtoleranz – nur bei
                      Größenmaßen zulässig.
"""
from __future__ import annotations

import re

from ..drawing.dimensions import DimKind, DimValue
from ..drawing.fcf import find_feature_frames
from .base import CheckContext

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
