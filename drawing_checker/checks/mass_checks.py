"""Plausibilitätsprüfung der Gewichtsangabe – auch ohne STEP-Datei.

Der Masseabgleich gegen das STEP-Modell (`geometry_checks.check_mass`) ist
die schärfste Prüfung, setzt aber ein STEP voraus. Weil ein großer Teil der
Pakete nur ein PDF enthält, prüft dieses Modul die Gewichtsangabe allein
gegen die Zeichnung:

  MASS.IMPOSSIBLE  Das Teil wäre schwerer als ein VOLLER Quader seiner
                   Hüllmaße. Physikalisch unmöglich – klassische Ursachen:
                   Einheit vertauscht (g/kg), Komma verrutscht, Gewicht aus
                   einer anderen Variante übernommen, falscher Werkstoff.
  MASS.TOO_LIGHT   Das Teil wäre fast nur Luft (Füllgrad < 1 %). Bei Blech-
                   und Schweißkonstruktionen möglich, sonst verdächtig.
  MASS.DENSITY_HINT Die Gewichtsangabe passt rechnerisch zu einem ANDEREN
                   Werkstoff als dem angegebenen (Volumen aus dem STEP).
                   Findet den häufigsten Fall „Schriftfeld kopiert".

Grundgedanke der Unmöglichkeitsprüfung:

    m = ρ · V_Teil   und   V_Teil ≤ V_Hüllquader
    =>  ρ_rechnerisch = m / V_Hüllquader ≤ ρ_Werkstoff

Weil die Hüllmaße aus den größten Zeichnungsmaßen geschätzt werden, ist der
Quader in aller Regel zu GROSS – das Urteil „unmöglich" ist damit auf der
sicheren Seite. Zusätzlich wird erst ab einem deutlichen Faktor gemeldet.
"""
from __future__ import annotations

import logging

from ..core.models import Severity
from ..drawing.dimensions import DimValue, estimate_envelope
from ..drawing.metadata import extract_weight_kg
from .base import CheckContext
from .materials import MATERIALS, find_materials

log = logging.getLogger(__name__)

# Verhältnis rechnerische Dichte / Werkstoffdichte, ab dem gemeldet wird.
DEFAULT_IMPOSSIBLE_FACTOR = 1.3     # 30 % Reserve für grobe Hüllmaßschätzung
DEFAULT_MIN_FILL = 0.01             # Füllgrad, unter dem es verdächtig wird
# Typische Zahlendreher: Faktor zwischen Angabe und Rechnung.
UNIT_FACTORS = {1000.0: "g statt kg", 100.0: "Komma zwei Stellen verrutscht",
                10.0: "Komma eine Stelle verrutscht"}


def check_mass_plausibility(ctx: CheckContext, dims: list[DimValue]) -> str:
    """Gewichtsangabe gegen die Hüllmaße der Zeichnung prüfen.

    Rückgabe: Kurztext für die Excel-Vergleichswerte ("" wenn nicht prüfbar).
    """
    if not (ctx.profile.enabled("MASS.IMPOSSIBLE")
            or ctx.profile.enabled("MASS.TOO_LIGHT")):
        return ""
    drawing_kg = extract_weight_kg(ctx.pdf)
    if drawing_kg is None:
        return ""
    density = _declared_density(ctx)
    if density is None:
        return ""
    box_cm3 = _envelope_volume_cm3(dims)
    if box_cm3 is None:
        return ""

    max_kg = box_cm3 * density / 1000.0        # g/cm³ · cm³ = g -> kg
    fill = drawing_kg / max_kg if max_kg else 0.0
    summary = (f"Masse-Plausibilität: {drawing_kg:.2f} kg, Hüllquader "
               f"{box_cm3:.0f} cm³ → Füllgrad {fill * 100:.0f} %")

    factor = float(ctx.profile.params.get("mass_impossible_factor",
                                          DEFAULT_IMPOSSIBLE_FACTOR))
    if fill > factor and ctx.profile.enabled("MASS.IMPOSSIBLE"):
        ctx.add("MASS.IMPOSSIBLE",
                f"Gewichtsangabe unmöglich: {drawing_kg:.2f} kg bei Hüllmaßen "
                f"{_envelope_text(dims)} – ein VOLLER Block aus diesem "
                f"Werkstoff wöge nur {max_kg:.2f} kg",
                detail=_explain(drawing_kg, max_kg, density, box_cm3))
    elif (fill < float(ctx.profile.params.get("mass_min_fill", DEFAULT_MIN_FILL))
          and ctx.profile.enabled("MASS.TOO_LIGHT")):
        ctx.add("MASS.TOO_LIGHT",
                f"Gewichtsangabe sehr klein: {drawing_kg:.3f} kg entspricht "
                f"{fill * 100:.1f} % des Hüllquaders ({max_kg:.1f} kg voll)",
                severity=ctx.profile.severity("MASS.TOO_LIGHT",
                                              Severity.WARNING),
                detail="Bei dünnen Blechen und Schweißrahmen möglich. Sonst "
                       "prüfen, ob die Einheit stimmt (g statt kg) oder das "
                       "Gewicht von einer kleineren Variante stammt.")
    return summary


def check_density_hint(ctx: CheckContext, model_volume_mm3: float) -> None:
    """Passt die Gewichtsangabe rechnerisch zu einem anderen Werkstoff?

    Wird nur mit STEP aufgerufen (exaktes Volumen). Der Hinweis ist die
    Diagnose zur Massenabweichung: „Angabe passt zu Stahl, angegeben ist
    Aluminium" – der Klassiker beim kopierten Schriftfeld.
    """
    if not ctx.profile.enabled("MASS.DENSITY_HINT") or model_volume_mm3 <= 0:
        return
    drawing_kg = extract_weight_kg(ctx.pdf)
    if drawing_kg is None:
        return
    declared = _declared_material(ctx)
    if declared is None or not declared.density:
        return
    volume_cm3 = model_volume_mm3 / 1000.0
    implied = drawing_kg * 1000.0 / volume_cm3      # g/cm³
    if abs(implied - declared.density) / declared.density <= 0.10:
        return                                      # passt zum Werkstoff

    match = _closest_material(implied, exclude=declared.name)
    if match is None:
        return
    ctx.add("MASS.DENSITY_HINT",
            f"Gewichtsangabe passt nicht zu {declared.name}: rechnerisch "
            f"{implied:.1f} g/cm³ – das entspricht {match.name} "
            f"({match.density} g/cm³)",
            detail=f"{drawing_kg:.2f} kg auf {volume_cm3:.0f} cm³ "
                   f"Modellvolumen. Häufige Ursache: Schriftfeld aus einer "
                   f"anderen Zeichnung übernommen, Werkstoff geändert ohne "
                   f"das Gewicht neu zu rechnen, oder falsche Variante im "
                   f"STEP. Erwartet für {declared.name}: "
                   f"{volume_cm3 * declared.density / 1000:.2f} kg.")


# ---------------------------------------------------------------- Intern
def _declared_material(ctx: CheckContext):
    hits = [h.material for h in find_materials(ctx) if h.material.density]
    return hits[0] if hits else None


def _declared_density(ctx: CheckContext) -> float | None:
    mat = _declared_material(ctx)
    return mat.density if mat else None


def _envelope_volume_cm3(dims: list[DimValue]) -> float | None:
    """Volumen des geschätzten Hüllquaders in cm³.

    Genutzt werden die drei größten unterschiedlichen Maße. Fehlt eine
    dritte Kante (typisch bei Wellen: nur Länge und Durchmesser bemaßt),
    wird die zweitgrößte doppelt verwendet – der Quader bleibt damit eine
    Obergrenze für das tatsächliche Bauteilvolumen.
    """
    env = estimate_envelope(dims, top_n=3)
    if len(env) < 2:
        return None
    a, b = env[0], env[1]
    c = env[2] if len(env) >= 3 else b
    volume = a * b * c / 1000.0
    return volume if volume > 0 else None


def _envelope_text(dims: list[DimValue]) -> str:
    env = estimate_envelope(dims, top_n=3)
    return "×".join(f"{v:g}" for v in env) + " mm"


def _explain(drawing_kg: float, max_kg: float, density: float,
             box_cm3: float) -> str:
    ratio = drawing_kg / max_kg if max_kg else 0.0
    hint = ""
    for factor, text in UNIT_FACTORS.items():
        if abs(ratio - factor) / factor < 0.35:
            hint = f" Der Faktor ≈ {factor:g} deutet auf {text} hin."
            break
    return (f"Hüllquader {box_cm3:.0f} cm³ × {density} g/cm³ = {max_kg:.2f} kg "
            f"als absolute Obergrenze; angegeben sind {drawing_kg:.2f} kg "
            f"({ratio:.1f}-faches).{hint} Die Hüllmaße stammen aus den "
            f"größten Zeichnungsmaßen und sind eher zu groß geschätzt – die "
            f"Angabe ist damit sicher zu hoch.")


def _closest_material(implied: float, exclude: str):
    """Werkstoff, dessen Dichte am besten zur Rechnung passt (±8 %)."""
    best = None
    best_dev = 0.08
    for mat in MATERIALS:
        if not mat.density or mat.name == exclude:
            continue
        dev = abs(mat.density - implied) / mat.density
        if dev < best_dev:
            best, best_dev = mat, dev
    return best
