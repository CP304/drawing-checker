"""Vertiefte Geometrieprüfungen: Masse und Bohrbild.

Ergänzen den Hüllmaß-Abgleich (step_compare) um zwei unabhängige Indizien
für "falsche Konfiguration gespeichert":

  GEO.MASS       Gewichtsangabe der Zeichnung vs. STEP-Volumen × Dichte
                 des erkannten Werkstoffs. Sehr trennscharf, weil Volumen
                 und Dichte unabhängig von der Bemaßungsqualität sind.
  GEO.HOLE_COUNT Explizite Mehrfachangaben der Zeichnung ("4×⌀18") vs.
                 tatsächlich im Modell vorhandene Bohrungen gleichen
                 Durchmessers.
  GEO.THREAD     Gewindeangaben ("M12") ohne passendes Kernloch im Modell.

Alle drei melden konservativ: Ein Treffer ist ein Prüfhinweis, kein
automatisches K.O. – nur grobe Abweichungen (Faktor) werden hart bewertet.
"""
from __future__ import annotations

import logging

from ..drawing.dimensions import DimKind, DimValue
from ..drawing.metadata import extract_weight_kg
from .base import CheckContext
from .materials import find_materials
from .step_compare import StepGeometry

log = logging.getLogger(__name__)

# Kernlochdurchmesser für metrisches Regelgewinde (ISO 261/ISO 262).
THREAD_CORE_DIA = {
    3: 2.5, 4: 3.3, 5: 4.2, 6: 5.0, 8: 6.8, 10: 8.5, 12: 10.2, 14: 12.0,
    16: 14.0, 18: 15.5, 20: 17.5, 22: 19.5, 24: 21.0, 27: 24.0, 30: 26.5,
    33: 29.5, 36: 32.0, 42: 37.5, 48: 43.0,
}


def check_mass(ctx: CheckContext, geometry: StepGeometry) -> str:
    """Vergleicht die Gewichtsangabe der Zeichnung mit dem STEP-Volumen.

    Rückgabe: Kurztext für die Excel-Vergleichswerte ("" wenn nicht prüfbar).
    """
    if not ctx.profile.enabled("GEO.MASS") or geometry.backend != "occ":
        return ""
    drawing_kg = extract_weight_kg(ctx.pdf)
    if drawing_kg is None:
        return ""
    hits = find_materials(ctx)
    density = next((h.material.density for h in hits if h.material.density),
                   None)
    if density is None:
        return ""
    model_kg = geometry.mass_kg(density)
    if not model_kg:
        return ""

    ratio = model_kg / drawing_kg if drawing_kg else 0.0
    summary = (f"Masse: Zeichnung {drawing_kg:.2f} kg vs. Modell "
               f"{model_kg:.2f} kg (Dichte {density} g/cm³)")
    warn_pct = float(ctx.profile.params.get("mass_warn_pct", 15)) / 100.0
    error_pct = float(ctx.profile.params.get("mass_error_pct", 40)) / 100.0
    deviation = abs(model_kg - drawing_kg) / drawing_kg

    if deviation > error_pct:
        ctx.add("GEO.MASS",
                f"Masse weicht stark ab: Zeichnung {drawing_kg:.2f} kg, "
                f"Modell {model_kg:.2f} kg ({deviation * 100:.0f} %)",
                detail=f"Volumen {geometry.volume / 1000:.0f} cm³ × Dichte "
                       f"{density} g/cm³. Faktor {ratio:.2f} – Hinweis auf "
                       f"falsche Konfiguration, falschen Werkstoff oder eine "
                       f"veraltete Gewichtsangabe.")
    elif deviation > warn_pct:
        ctx.add("GEO.MASS",
                f"Masse plausibel, aber abweichend: Zeichnung "
                f"{drawing_kg:.2f} kg, Modell {model_kg:.2f} kg "
                f"({deviation * 100:.0f} %)",
                severity=ctx.profile.severity("GEO.MASS_MINOR"),
                detail="Bei Guss-/Schweißteilen und Rohteilgewichten normal – "
                       "sonst Gewichtsangabe im Schriftfeld aktualisieren.")
    return summary


def check_hole_pattern(ctx: CheckContext, geometry: StepGeometry,
                       dims: list[DimValue]) -> str:
    """Explizite Bohrbildangaben ("4×⌀18") gegen das Modell prüfen."""
    if not ctx.profile.enabled("GEO.HOLE_COUNT") or geometry.backend != "occ":
        return ""
    # Nur eindeutige Mehrfachangaben auswerten – Einzelnennungen sagen
    # nichts über die Stückzahl aus (dasselbe Maß kann mehrfach im Blatt
    # stehen), und koaxiale Absätze fasst das Modell zusammen.
    explicit = [d for d in dims
                if d.kind is DimKind.DIAMETER and d.count > 1]
    if not explicit:
        return ""
    tol = float(ctx.profile.params.get("hole_dia_tol", 0.6))
    notes: list[str] = []
    for d in explicit:
        found = sum(n for dia, n in geometry.holes.items()
                    if abs(dia - d.value) <= tol)
        notes.append(f"{d.count}×⌀{d.value:g}→{found}")
        if found == 0:
            ctx.add("GEO.HOLE_COUNT",
                    f"Zeichnung fordert {d.count}×⌀{d.value:g}, im Modell "
                    f"ist keine Bohrung dieses Durchmessers vorhanden",
                    bbox=d.bbox, page=d.page,
                    detail="Bohrbild fehlt im STEP – falsche Konfiguration "
                           "oder Modell ohne Bohrungen (Rohteil?).")
        elif found < d.count:
            ctx.add("GEO.HOLE_COUNT",
                    f"Bohrbild weicht ab: Zeichnung {d.count}×⌀{d.value:g}, "
                    f"Modell {found}×",
                    severity=ctx.profile.severity("GEO.HOLE_COUNT_MINOR"),
                    bbox=d.bbox, page=d.page,
                    detail="Teilbohrungen/Symmetrieangaben können die Zählung "
                           "verkürzen – bitte visuell prüfen.")
    return "Bohrbild " + ", ".join(notes) if notes else ""


def check_threads(ctx: CheckContext, geometry: StepGeometry,
                  dims: list[DimValue]) -> None:
    """Gewindeangaben ohne passendes Kernloch im Modell."""
    if not ctx.profile.enabled("GEO.THREAD") or geometry.backend != "occ":
        return
    threads = {round(d.value, 1): d for d in dims if d.kind is DimKind.THREAD}
    if not threads:
        return
    if not geometry.holes:
        return  # Modell ohne jede Bohrung: Fall deckt GEO.HOLE_COUNT ab
    tol = float(ctx.profile.params.get("thread_core_tol", 0.8))
    missing = []
    for nominal, dim in threads.items():
        core = THREAD_CORE_DIA.get(int(nominal))
        if core is None:
            continue
        # Kernloch ODER Durchgangsloch (Nenndurchmesser) akzeptieren –
        # viele Modelle zeigen das Gewinde als glatte Bohrung.
        ok = any(abs(dia - core) <= tol or abs(dia - nominal) <= tol
                 for dia in geometry.holes)
        if not ok:
            missing.append((nominal, core, dim))
    for nominal, core, dim in missing[:5]:
        ctx.add("GEO.THREAD",
                f"Gewinde M{nominal:g} auf der Zeichnung, im Modell kein "
                f"passendes Loch (Kern ⌀{core}, Nenn ⌀{nominal:g})",
                bbox=dim.bbox, page=dim.page,
                detail="Gewinde werden im STEP oft als glatte Bohrung "
                       "modelliert – fehlt auch die, passt das Modell nicht "
                       "zur Zeichnung.")
