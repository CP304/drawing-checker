"""Maßstabsbasierte Prüfungen: gemessene Ansicht statt Maßtext.

Aus Schriftfeld-Maßstab und der gemessenen Größe der Zeichnungsansicht
ergibt sich die Bauteilgröße – völlig unabhängig von der Maßtext-Extraktion.
Das liefert zwei Prüfungen:

  SCALE.MISMATCH   Gemessene Ansicht passt nicht zu den eingetragenen Maßen:
                   entweder ist die Zeichnung nicht maßstäblich oder der
                   Maßstab im Schriftfeld ist falsch.
  GEO.VIEW_SIZE    Gemessene Ansicht passt nicht zum STEP-Modell. Greift
                   auch dann, wenn die Maßextraktion nichts hergibt
                   (schlechter Textlayer, OCR).

Beide sind bewusst großzügig toleriert: Detail- und Schnittansichten mit
abweichendem Maßstab, Bemaßungsüberstände und gerundete Maßstabsangaben
dürfen nicht zu Fehlalarmen führen.
"""
from __future__ import annotations

import logging

from ..drawing.dimensions import DimKind, DimValue
from ..drawing.metadata import extract_scale, mm_per_point
from .base import CheckContext

log = logging.getLogger(__name__)


def measure_largest_view(ctx: CheckContext, scale: float
                         ) -> tuple[float, float, object] | None:
    """Größte Zeichnungsansicht in Bauteil-Millimetern.

    Rückgabe: (Breite, Höhe, Ansicht) oder None.
    """
    from .contour_projection import extract_views

    try:
        views = extract_views(ctx.pdf)
    except Exception:  # Stub-PDFs in Tests
        return None
    if not views:
        return None
    factor = mm_per_point(scale)
    best = None
    for v in views:
        x0, y0, x1, y1 = v.bbox
        w, h = (x1 - x0) * factor, (y1 - y0) * factor
        if best is None or w * h > best[0] * best[1]:
            best = (w, h, v)
    return best


def check_scale_consistency(ctx: CheckContext, dims: list[DimValue]) -> str:
    """Gemessene Ansichtsgröße gegen die eingetragenen Maße prüfen.

    Rückgabe: Kurztext für die Excel-Vergleichswerte.
    """
    scale = extract_scale(ctx.pdf)
    if scale is None:
        return ""
    measured = measure_largest_view(ctx, scale)
    if measured is None:
        return ""
    width, height, view = measured
    largest_view = max(width, height)
    if largest_view < 1:
        return ""

    values = [d.value for d in dims
              if d.kind in (DimKind.LINEAR, DimKind.DIAMETER)]
    summary = (f"Ansicht gemessen {width:.0f} × {height:.0f} mm "
               f"(Maßstab 1:{scale:g})")
    if not values:
        return summary
    if not ctx.profile.enabled("SCALE.MISMATCH"):
        return summary        # nur messen, nicht bewerten
    largest_dim = max(values)
    tol = float(ctx.profile.params.get("scale_tol", 0.15))
    # Bewusst einseitig: Eine Ansicht kann durch unvollständig erkannte
    # Konturlinien zu KLEIN gemessen werden – das ist kein Zeichnungsfehler.
    # Nur eine Ansicht, die GRÖSSER ist als das größte eingetragene Maß,
    # ist ein sicheres Zeichen für einen falschen Maßstab.
    deviation = (largest_view - largest_dim) / max(largest_dim, 1)
    if deviation > tol:
        ctx.add("SCALE.MISMATCH",
                f"Zeichnung nicht maßstäblich: gemessene Ansicht "
                f"{largest_view:.0f} mm überschreitet das größte eingetragene "
                f"Maß ({largest_dim:g} mm) bei Maßstab 1:{scale:g}",
                bbox=_view_bbox(view), page=0,
                detail="Entweder stimmt der Maßstab im Schriftfeld nicht, "
                       "oder die Ansicht wurde nachträglich verzerrt/skaliert. "
                       "Für den Lieferanten ist die Zeichnung dann nur noch "
                       "über die Maßzahlen nutzbar.")
    return summary


def check_view_vs_model(ctx: CheckContext, geometry, dims: list[DimValue]
                        ) -> None:
    """Gemessene Ansichtsgröße gegen die Modell-Bounding-Box prüfen.

    Unabhängig von den Maßtexten – deshalb auch bei schwachem Textlayer
    aussagekräftig.
    """
    if not ctx.profile.enabled("GEO.VIEW_SIZE") or geometry.backend != "occ":
        return
    scale = extract_scale(ctx.pdf)
    if scale is None:
        return
    measured = measure_largest_view(ctx, scale)
    if measured is None:
        return
    width, height, view = measured
    largest_view = max(width, height)
    obb_max = geometry.obb_dims[0]
    if largest_view < 1 or obb_max <= 0:
        return
    tol = float(ctx.profile.params.get("view_model_tol", 0.2))
    # Ebenfalls einseitig (s. check_scale_consistency): zu klein gemessene
    # Ansichten sind ein Erkennungs-, kein Zeichnungsproblem.
    deviation = (largest_view - obb_max) / obb_max
    if deviation <= tol:
        return
    # Bei bereits erkanntem Einheiten- oder Maßstabsfehler nicht doppelt melden.
    known = {f.code for f in ctx.findings}
    if {"GEO.UNIT_MISMATCH", "SCALE.MISMATCH"} & known:
        return
    ctx.add("GEO.VIEW_SIZE",
            f"Gemessene Ansicht ({largest_view:.0f} mm) ist größer als das "
            f"Modell ({obb_max:.0f} mm)",
            bbox=_view_bbox(view), page=0,
            detail=f"Abweichung {deviation * 100:.0f} % bei Maßstab "
                   f"1:{scale:g}. Unabhängig von den Maßzahlen gemessen – "
                   f"stützt den Verdacht auf ein falsch zugeordnetes Modell.")


def _view_bbox(view):
    from ..core.models import BBox

    x0, y0, x1, y1 = view.bbox
    return BBox(x0, y0, x1, y1)
