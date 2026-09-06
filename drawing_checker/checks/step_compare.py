"""Geometrieabgleich: STEP-Modell gegen die aus der Zeichnung ermittelten Maße.

Ziel: falsch gespeicherte Konfigurationen erkennen (Zeichnung und 3D-Modell
gehören nicht zusammen).

Zwei Backends:
  * OCC (cadquery-ocp / OpenCascade): exakte optimale Bounding-Box (OBB,
    orientierungsunabhängig), Volumen, Zylinderflächen-Durchmesser.
  * Fallback ohne OCC: Punktwolke aller CARTESIAN_POINT-Einträge der
    STEP-Datei, PCA-orientierte Bounding-Box. Kein Volumen, keine Zylinder.

Ergebnis ist bewusst dreistufig: passt / passt nicht / nicht sicher bewertbar.
Bei Guss-/Schweißprofilen sind die Toleranzbänder größer und "passt nicht"
wird per Profil auf warning herabgestuft (siehe rules/profiles.yaml).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..drawing.dimensions import DimKind, DimValue, estimate_envelope
from .base import CheckContext

log = logging.getLogger(__name__)


@dataclass
class StepGeometry:
    obb_dims: tuple[float, float, float]      # Kantenlängen der OBB, absteigend
    volume: float | None = None               # mm³ (nur OCC)
    cylinder_diameters: list[float] = field(default_factory=list)  # nur OCC
    backend: str = "fallback"
    point_count: int = 0

    @property
    def diagonal(self) -> float:
        a, b, c = self.obb_dims
        return (a * a + b * b + c * c) ** 0.5


class StepError(Exception):
    pass


# ---------------------------------------------------------------- Backends
def analyze_step(path: Path) -> StepGeometry:
    try:
        return _analyze_occ(path)
    except ImportError:
        log.info("OCP nicht verfügbar – nutze Punktwolken-Fallback für %s", path.name)
        return _analyze_pointcloud(path)


def _analyze_occ(path: Path) -> StepGeometry:
    from OCP.Bnd import Bnd_OBB
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise StepError(f"STEP-Datei nicht lesbar: {path}")
    reader.TransferRoots()
    shape = reader.OneShape()
    if shape.IsNull():
        raise StepError(f"STEP-Datei enthält keine Geometrie: {path}")

    obb = Bnd_OBB()
    BRepBndLib.AddOBB_s(shape, obb, True, True, True)
    dims = tuple(sorted(
        (2 * obb.XHSize(), 2 * obb.YHSize(), 2 * obb.ZHSize()), reverse=True))

    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    volume = max(props.Mass(), 0.0)

    diameters: set[float] = set()
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face(exp.Current())
        surf = BRepAdaptor_Surface(face)
        if surf.GetType() == GeomAbs_Cylinder:
            diameters.add(round(2 * surf.Cylinder().Radius(), 2))
        exp.Next()

    return StepGeometry(
        obb_dims=dims, volume=volume,
        cylinder_diameters=sorted(diameters, reverse=True), backend="occ",
    )


RE_CARTESIAN = re.compile(
    r"CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(\s*"
    r"(-?[\d.Ee+-]+)\s*,\s*(-?[\d.Ee+-]+)\s*,\s*(-?[\d.Ee+-]+)\s*\)\s*\)"
)


def _analyze_pointcloud(path: Path) -> StepGeometry:
    """PCA-orientierte Bounding-Box über alle kartesischen Punkte der Datei.

    Kontrollpunkte von Freiformflächen können leicht außerhalb der Geometrie
    liegen – für den Konfigurationsabgleich (grobe Hüllmaße) ist das ausreichend.
    """
    import numpy as np

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise StepError(f"STEP-Datei nicht lesbar: {path} ({exc})") from exc
    pts = np.array(
        [[float(a), float(b), float(c)] for a, b, c in RE_CARTESIAN.findall(text)],
        dtype=float,
    )
    if len(pts) < 4:
        raise StepError(f"Keine auswertbaren Punkte in STEP-Datei: {path}")

    centered = pts - pts.mean(axis=0)
    cov = np.cov(centered.T)
    _eigval, eigvec = np.linalg.eigh(cov)
    proj = centered @ eigvec
    extents = proj.max(axis=0) - proj.min(axis=0)
    dims = tuple(sorted((float(x) for x in extents), reverse=True))
    return StepGeometry(obb_dims=dims, backend="fallback", point_count=len(pts))


# ----------------------------------------------------------------- Abgleich
@dataclass
class CompareResult:
    verdict: str            # "passt" | "passt_nicht" | "unsicher"
    summary: str            # menschenlesbare Vergleichswerte (für Excel)
    detail: str = ""


def _tol(profile, value: float) -> float:
    t = profile.step_tolerance
    return max(float(t.get("rel", 0.05)) * value, float(t.get("abs", 2.0)))


def compare_step_to_drawing(
    geometry: StepGeometry, dims: list[DimValue], profile
) -> CompareResult:
    envelope = estimate_envelope(dims)
    obb = geometry.obb_dims
    summary_parts = [
        f"STEP-OBB {obb[0]:.1f} × {obb[1]:.1f} × {obb[2]:.1f} mm"
        + (f", V={geometry.volume / 1000.0:.1f} cm³" if geometry.volume else "")
        + f" [{geometry.backend}]",
        "Zeichnungsmaße (Top): " + (
            ", ".join(f"{v:g}" for v in envelope) if envelope else "keine extrahiert"),
    ]
    summary = " | ".join(summary_parts)

    if not envelope:
        return CompareResult("unsicher", summary,
                             "Keine Maße aus der Zeichnung extrahierbar.")

    # 1) Hauptmaß: das größte Zeichnungsmaß muss zur größten OBB-Kante passen.
    main = envelope[0]
    main_dev = abs(main - obb[0])
    main_ok = main_dev <= _tol(profile, main)

    # 2) Kein Zeichnungsmaß darf größer als die Raumdiagonale des STEP sein.
    diag = geometry.diagonal
    oversized = [v for v in envelope if v > diag + _tol(profile, v)]

    # 3) Wie viele Top-Maße finden eine Entsprechung in einer OBB-Kante,
    #    der Diagonale einer OBB-Seitenfläche oder einem Zylinderdurchmesser?
    face_diags = [
        (obb[0] ** 2 + obb[1] ** 2) ** 0.5,
        (obb[0] ** 2 + obb[2] ** 2) ** 0.5,
        (obb[1] ** 2 + obb[2] ** 2) ** 0.5,
    ]
    targets = list(obb) + face_diags + list(geometry.cylinder_diameters)
    matched = sum(
        1 for v in envelope
        if any(abs(v - t) <= _tol(profile, v) for t in targets)
    )
    ratio = matched / len(envelope)

    drawing_dia = sorted(
        {round(d.value, 2) for d in dims if d.kind == DimKind.DIAMETER}, reverse=True)
    dia_note = ""
    if drawing_dia and geometry.cylinder_diameters:
        hits = sum(
            1 for v in drawing_dia
            if any(abs(v - c) <= _tol(profile, v) for c in geometry.cylinder_diameters)
        )
        dia_note = f" ⌀-Treffer: {hits}/{len(drawing_dia)}."

    detail = (f"Hauptmaß {main:g} vs. OBB {obb[0]:.1f} "
              f"(Abw. {main_dev:.1f} mm). Maß-Zuordnung: {matched}/{len(envelope)}."
              + dia_note)

    if oversized:
        return CompareResult(
            "passt_nicht", summary,
            f"Zeichnungsmaß(e) {', '.join(f'{v:g}' for v in oversized)} mm größer "
            f"als die STEP-Raumdiagonale ({diag:.1f} mm). " + detail)
    # Hinweis: Zwischenmaße (Absatzlängen, Lochabstände) finden naturgemäß
    # keine OBB-Entsprechung – deshalb genügt neben dem Hauptmaß eine
    # moderate Zuordnungsquote für "passt".
    if main_ok and ratio >= 0.3:
        return CompareResult("passt", summary, detail)
    if not main_ok and ratio < 0.34:
        return CompareResult("passt_nicht", summary, detail)
    return CompareResult("unsicher", summary, detail)


def check_step(ctx: CheckContext, dims: list[DimValue]) -> str:
    """Führt den kompletten STEP-Check aus; liefert die Summary für Excel."""
    step = ctx.package.step_file
    if step is None:
        if ctx.profile.enabled("DOC.NO_STEP"):
            ctx.add("DOC.NO_STEP",
                    "Kein STEP im Paket – Geometrieprüfung entfällt")
        return ""
    try:
        geometry = analyze_step(step)
    except StepError as exc:
        ctx.add("GEO.UNCERTAIN", f"STEP-Datei nicht auswertbar: {exc}")
        return ""

    result = compare_step_to_drawing(geometry, dims, ctx.profile)
    if result.verdict == "passt_nicht":
        ctx.add("GEO.MISMATCH",
                "Geometrie passt nicht zur Zeichnung – vermutlich falsche "
                "Konfiguration gespeichert", detail=result.detail)
    elif result.verdict == "unsicher":
        ctx.add("GEO.UNCERTAIN",
                "Geometrieabgleich nicht sicher bewertbar – bitte manuell prüfen",
                detail=result.detail)
    if not dims and ctx.profile.enabled("GEO.NO_DIMS"):
        ctx.add("GEO.NO_DIMS",
                "Keine Maße aus der Zeichnung extrahierbar (Geometrieabgleich "
                "nur eingeschränkt möglich)")
    return result.summary
