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
    # Bohrbild aus dem Modell: {Durchmesser: Anzahl} – getrennt nach
    # Innenzylindern (Bohrungen) und Außenzylindern (Wellen/Zapfen).
    holes: dict[float, int] = field(default_factory=dict)
    shafts: dict[float, int] = field(default_factory=dict)
    planar_faces: int = 0
    face_count: int = 0
    solid_count: int = 1          # Volumenkörper im Modell
    disjoint_solids: int = 1      # davon räumlich getrennt (echte Baugruppe)
    backend: str = "fallback"
    point_count: int = 0

    @property
    def diagonal(self) -> float:
        a, b, c = self.obb_dims
        return (a * a + b * b + c * c) ** 0.5

    def mass_kg(self, density_g_cm3: float) -> float | None:
        """Masse aus Volumen und Werkstoffdichte (g/cm³) in kg."""
        if not self.volume or density_g_cm3 <= 0:
            return None
        return self.volume / 1000.0 * density_g_cm3 / 1000.0


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

    # Getrennte Volumenkörper zählen (Baugruppe vs. Einzelteil)
    from OCP.TopAbs import TopAbs_SOLID

    from OCP.Bnd import Bnd_Box

    solid_boxes = []
    sexp = TopExp_Explorer(shape, TopAbs_SOLID)
    while sexp.More():
        box = Bnd_Box()
        BRepBndLib.Add_s(sexp.Current(), box, True)
        if not box.IsVoid():
            solid_boxes.append((box.GetXMin(), box.GetYMin(), box.GetZMin(),
                                box.GetXMax(), box.GetYMax(), box.GetZMax()))
        sexp.Next()
    solids = len(solid_boxes)
    disjoint = _count_disjoint_groups(solid_boxes)

    obb = Bnd_OBB()
    BRepBndLib.AddOBB_s(shape, obb, True, True, True)
    dims = tuple(sorted(
        (2 * obb.XHSize(), 2 * obb.YHSize(), 2 * obb.ZHSize()), reverse=True))

    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    volume = max(props.Mass(), 0.0)

    # Zylinderflächen einsammeln und zu physischen Bohrungen/Zapfen
    # zusammenfassen: mehrere Teilflächen derselben Achse gehören zusammen.
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.TopAbs import TopAbs_REVERSED

    cylinders: dict[tuple, dict] = {}
    planar = 0
    n_faces = 0
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face(exp.Current())
        n_faces += 1
        surf = BRepAdaptor_Surface(face)
        stype = surf.GetType()
        if stype == GeomAbs_Plane:
            planar += 1
        elif stype == GeomAbs_Cylinder:
            cyl = surf.Cylinder()
            radius = cyl.Radius()
            ax = cyl.Axis()
            d, loc = ax.Direction(), ax.Location()
            # Achsschlüssel: Richtung (vorzeichenneutral) + Aufpunkt, auf die
            # Ebene senkrecht zur Achse projiziert -> identisch für alle
            # Teilflächen derselben Bohrung.
            dir_key = _axis_dir_key(d.X(), d.Y(), d.Z())
            perp = _perp_offset((loc.X(), loc.Y(), loc.Z()),
                                (d.X(), d.Y(), d.Z()))
            key = (round(radius, 2), dir_key, perp)
            entry = cylinders.setdefault(
                key, {"radius": radius, "inner": 0, "outer": 0})
            if face.Orientation() == TopAbs_REVERSED:
                entry["inner"] += 1
            else:
                entry["outer"] += 1
        exp.Next()

    holes: dict[float, int] = {}
    shafts: dict[float, int] = {}
    for entry in cylinders.values():
        dia = round(2 * entry["radius"], 2)
        target = holes if entry["inner"] >= entry["outer"] else shafts
        target[dia] = target.get(dia, 0) + 1

    diameters = sorted({*holes, *shafts}, reverse=True)
    return StepGeometry(
        obb_dims=dims, volume=volume, cylinder_diameters=diameters,
        holes=holes, shafts=shafts, planar_faces=planar, face_count=n_faces,
        solid_count=max(solids, 1), disjoint_solids=max(disjoint, 1),
        backend="occ",
    )


def _count_disjoint_groups(boxes: list[tuple], slack: float = 0.01) -> int:
    """Zählt räumlich getrennte Körpergruppen anhand ihrer Bounding-Boxen.

    Sich berührende oder überlappende Körper gehören zu einem Bauteil
    (nur nicht verschmolzen); getrennte Gruppen sind eine echte Baugruppe.
    """
    n = len(boxes)
    if n <= 1:
        return n
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def overlaps(a, b):
        ax0, ay0, az0, ax1, ay1, az1 = a
        bx0, by0, bz0, bx1, by1, bz1 = b
        return (ax0 - slack <= bx1 and bx0 - slack <= ax1
                and ay0 - slack <= by1 and by0 - slack <= ay1
                and az0 - slack <= bz1 and bz0 - slack <= az1)

    for i in range(n):
        for j in range(i + 1, n):
            if overlaps(boxes[i], boxes[j]):
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[rj] = ri
    return len({find(i) for i in range(n)})


def _axis_dir_key(x: float, y: float, z: float, ndigits: int = 2) -> tuple:
    """Richtungsschlüssel ohne Vorzeichen (Achse ±d ist dieselbe Achse)."""
    v = (x, y, z)
    # Vorzeichen an der ersten signifikanten Komponente normieren
    for c in v:
        if abs(c) > 1e-9:
            if c < 0:
                v = (-x, -y, -z)
            break
    return tuple(round(c, ndigits) for c in v)


def _perp_offset(point: tuple, direction: tuple, ndigits: int = 1) -> tuple:
    """Aufpunkt der Achse, senkrecht zur Achsrichtung projiziert."""
    px, py, pz = point
    dx, dy, dz = direction
    norm = (dx * dx + dy * dy + dz * dz) ** 0.5 or 1.0
    dx, dy, dz = dx / norm, dy / norm, dz / norm
    t = px * dx + py * dy + pz * dz
    return (round(px - t * dx, ndigits), round(py - t * dy, ndigits),
            round(pz - t * dz, ndigits))


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
    main_ok: bool = False   # größtes Zeichnungsmaß passt zur größten OBB-Kante


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
            f"als die STEP-Raumdiagonale ({diag:.1f} mm). " + detail,
            main_ok=main_ok)
    # Hinweis: Zwischenmaße (Absatzlängen, Lochabstände) finden naturgemäß
    # keine OBB-Entsprechung – deshalb genügt neben dem Hauptmaß eine
    # moderate Zuordnungsquote für "passt".
    if main_ok and ratio >= 0.3:
        return CompareResult("passt", summary, detail, main_ok=True)
    if not main_ok and ratio < 0.34:
        return CompareResult("passt_nicht", summary, detail, main_ok=False)
    return CompareResult("unsicher", summary, detail, main_ok=main_ok)


def _apply_contour_stage(ctx: CheckContext, step: Path, result: CompareResult,
                         geometry: StepGeometry) -> CompareResult:
    """Ausbaustufe Konturprojektion: schärft das Maß-Urteil, ersetzt es nicht.

    * "unsicher" + klar guter Kontur-Score + Hauptmaß ok  -> "passt"
    * "passt"    + klar schlechter Kontur-Score           -> "unsicher"
    * "passt_nicht" bleibt immer bestehen.
    Läuft nur mit OCC-Backend und wenn GEO.CONTOUR im Profil aktiv ist.
    """
    if not ctx.profile.enabled("GEO.CONTOUR") or geometry.backend != "occ":
        return result
    if result.verdict == "passt_nicht":
        return result
    try:
        from .contour_projection import SCORE_BAD, SCORE_GOOD, compare_contours

        contour = compare_contours(ctx.pdf, step)
    except ImportError:
        return result
    except Exception as exc:
        log.warning("Konturprojektion fehlgeschlagen für %s: %s", step.name, exc)
        return result
    if contour.views_used == 0:
        return result

    summary = result.summary + (
        f" | Kontur-Score {contour.score:.2f} ({contour.views_used} Ansichten)")
    detail = result.detail + " " + contour.detail
    verdict = result.verdict
    if verdict == "unsicher" and contour.score >= SCORE_GOOD and result.main_ok:
        verdict = "passt"
        detail += " Konturprojektion bestätigt die Zuordnung."
    elif verdict == "passt" and contour.score <= SCORE_BAD:
        verdict = "unsicher"
        detail += (" Konturprojektion widerspricht trotz passender Maße – "
                   "bitte Sichtprüfung.")
    return CompareResult(verdict, summary, detail, main_ok=result.main_ok)


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
    result = _apply_contour_stage(ctx, step, result, geometry)

    # Vertiefte Einzelprüfungen (unabhängig vom Hüllmaß-Urteil)
    from .geometry_checks import (
        check_assembly_vs_part, check_hole_pattern, check_mass,
        check_threads, check_unit_mismatch,
    )

    unit_error = check_unit_mismatch(ctx, geometry, dims)
    extra = [check_mass(ctx, geometry), check_hole_pattern(ctx, geometry, dims)]
    if geometry.backend == "occ" and geometry.volume:
        # Diagnose zur Massenabweichung: passt die Gewichtsangabe zu einem
        # ANDEREN Werkstoff? (kopiertes Schriftfeld, Werkstoff geändert)
        from .mass_checks import check_density_hint

        check_density_hint(ctx, geometry.volume)
    check_threads(ctx, geometry, dims)
    check_assembly_vs_part(ctx, geometry)
    from .scale_checks import check_view_vs_model

    check_view_vs_model(ctx, geometry, dims)
    if unit_error:
        # Bei falscher Einheit sind Hüllmaß-Abweichungen die Folge, nicht die
        # Ursache – den Maß-Mismatch dann nicht zusätzlich als K.O. melden.
        ctx.findings = [f for f in ctx.findings if f.code != "GEO.MISMATCH"]
        result = CompareResult("unsicher", result.summary,
                               result.detail + " (Einheitenfehler erkannt)")
    if result.verdict == "passt_nicht" and ctx.pdf.ocr_used:
        # Maße aus OCR sind nicht sicher genug für ein K.O.-Urteil: ein
        # falsch gelesenes Maß darf keine Zeichnung sperren.
        ctx.add("GEO.UNCERTAIN",
                "Geometrie passt rechnerisch nicht – die Maße stammen aber "
                "aus OCR, deshalb nur als Prüfhinweis",
                detail=result.detail + " " + ctx.pdf.ocr_note())
    elif result.verdict == "passt_nicht":
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
    return " | ".join([result.summary, *[e for e in extra if e]])
