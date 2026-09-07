"""Abgleich Zeichnung gegen STEP-Modell.

Huellmass, Bohrbild, Gewindekern, Spiegelung, Einheiten - und die
Silhouetten-Projektion, die das Modell so darstellt, wie es die Ansicht
zeigen muesste. Alles OpenCascade-Code liegt hier beisammen; die
Importe sind bewusst traege, damit das Tool ohne OCP startet.
"""
from __future__ import annotations

# ======================================================================
# geometry_checks
# ======================================================================
# Vertiefte Geometrieprüfungen: Masse und Bohrbild.
#
# Ergänzen den Hüllmaß-Abgleich (step_compare) um zwei unabhängige Indizien
# für "falsche Konfiguration gespeichert":
#
#   GEO.MASS       Gewichtsangabe der Zeichnung vs. STEP-Volumen × Dichte
#                  des erkannten Werkstoffs. Sehr trennscharf, weil Volumen
#                  und Dichte unabhängig von der Bemaßungsqualität sind.
#   GEO.HOLE_COUNT Explizite Mehrfachangaben der Zeichnung ("4×⌀18") vs.
#                  tatsächlich im Modell vorhandene Bohrungen gleichen
#                  Durchmessers.
#   GEO.THREAD     Gewindeangaben ("M12") ohne passendes Kernloch im Modell.
#
# Alle drei melden konservativ: Ein Treffer ist ein Prüfhinweis, kein
# automatisches K.O. – nur grobe Abweichungen (Faktor) werden hart bewertet.



import logging

from .zeichnung import DimKind, DimValue
from .zeichnung import extract_weight_kg
from .regeln import CheckContext
from .pruef_werkstoff import find_materials

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


# Faktor zwischen Zoll und Millimeter – der Klassiker bei internationalem
# Datenaustausch (STEP in inch exportiert, Zeichnung in mm bemaßt).
INCH_MM = 25.4


def check_unit_mismatch(ctx: CheckContext, geometry: StepGeometry,
                        dims: list[DimValue]) -> bool:
    """Zoll/mm-Verwechslung zwischen Zeichnung und Modell erkennen.

    Liegt das Verhältnis des größten Zeichnungsmaßes zur längsten
    Modellkante nahe 25,4 (oder 1/25,4), ist das Modell in der falschen
    Einheit exportiert – ein Fehler, der wie eine falsche Konfiguration
    aussieht, aber eine ganz andere Ursache (und Lösung) hat.

    Rückgabe: True, wenn ein Einheitenfehler gemeldet wurde.
    """
    if not ctx.profile.enabled("GEO.UNIT_MISMATCH"):
        return False
    envelope = [d.value for d in dims
                if d.kind in (DimKind.LINEAR, DimKind.DIAMETER)]
    if not envelope or not geometry.obb_dims[0]:
        return False
    ratio = max(envelope) / geometry.obb_dims[0]
    tol = float(ctx.profile.params.get("unit_ratio_tol", 0.06))
    for factor, text in ((INCH_MM, "Modell in Zoll, Zeichnung in mm"),
                         (1 / INCH_MM, "Modell in mm, Zeichnung in Zoll")):
        if abs(ratio - factor) / factor <= tol:
            ctx.add("GEO.UNIT_MISMATCH",
                    f"Einheiten-Verwechslung wahrscheinlich: {text} "
                    f"(Verhältnis {ratio:.1f} ≈ {factor:.3g})",
                    detail="STEP-Datei mit der richtigen Längeneinheit neu "
                           "exportieren; die Geometrie selbst ist vermutlich "
                           "korrekt.")
            return True
    return False


def check_assembly_vs_part(ctx: CheckContext, geometry: StepGeometry) -> None:
    """Baugruppe im Modell, aber Einzelteilzeichnung (oder umgekehrt)."""
    if not ctx.profile.enabled("GEO.ASSEMBLY") or geometry.backend != "occ":
        return
    from .pruef_zeichnung import RE_BOM_HEADER

    has_bom = bool(RE_BOM_HEADER.search(ctx.pdf.full_text()))
    if geometry.disjoint_solids > 1 and not has_bom:
        ctx.add("GEO.ASSEMBLY",
                f"Modell enthält {geometry.disjoint_solids} räumlich getrennte "
                f"Körper, die Zeichnung ist aber ein Einzelteil "
                f"(keine Stückliste)",
                detail="Vermutlich wurde die Baugruppe statt des Einzelteils "
                       "gespeichert – falsches Dokument im Paket.")
    elif (geometry.solid_count > 1 and geometry.disjoint_solids == 1
            and ctx.profile.enabled("GEO.NOT_FUSED")):
        ctx.add("GEO.NOT_FUSED",
                f"Modell besteht aus {geometry.solid_count} sich berührenden, "
                f"nicht verschmolzenen Körpern",
                severity=ctx.profile.severity("GEO.NOT_FUSED"),
                detail="Volumen- und Masseberechnung bleiben korrekt, aber "
                       "das Modell ist kein sauberer Einzelkörper – für "
                       "Folgeprozesse (CAM, FEM) oft problematisch.")
    elif geometry.disjoint_solids == 1 and geometry.solid_count == 1 and has_bom:
        ctx.add("GEO.ASSEMBLY",
                "Zeichnung enthält eine Stückliste, das Modell aber nur einen "
                "Körper",
                severity=ctx.profile.severity("GEO.ASSEMBLY_MINOR"),
                detail="Bei Baugruppenzeichnungen sollte das Modell die "
                       "Einzelteile enthalten – bitte prüfen, ob das richtige "
                       "Dokument hinterlegt ist.")


# ======================================================================
# step_compare
# ======================================================================
# Geometrieabgleich: STEP-Modell gegen die aus der Zeichnung ermittelten Maße.
#
# Ziel: falsch gespeicherte Konfigurationen erkennen (Zeichnung und 3D-Modell
# gehören nicht zusammen).
#
# Zwei Backends:
#   * OCC (cadquery-ocp / OpenCascade): exakte optimale Bounding-Box (OBB,
#     orientierungsunabhängig), Volumen, Zylinderflächen-Durchmesser.
#   * Fallback ohne OCC: Punktwolke aller CARTESIAN_POINT-Einträge der
#     STEP-Datei, PCA-orientierte Bounding-Box. Kein Volumen, keine Zylinder.
#
# Ergebnis ist bewusst dreistufig: passt / passt nicht / nicht sicher bewertbar.
# Bei Guss-/Schweißprofilen sind die Toleranzbänder größer und "passt nicht"
# wird per Profil auf warning herabgestuft (siehe rules/profiles.yaml).



import gc
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from .zeichnung import DimKind, DimValue, estimate_envelope
from .regeln import CheckContext



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
    """STEP auswerten und den OpenCascade-Speicher wieder freigeben.

    Wichtig für den Dauerlauf: Der STEP-Leser hält das übertragene Modell
    fest (~25 MB je Datei). Ohne das ausdrückliche Freigeben unten wächst
    der Prozess über eine Materialgruppe um Gigabyte und stirbt irgendwann
    – gemessen mit `python -m tools.messen langlauf`.
    """
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
    try:
        if reader.ReadFile(str(path)) != IFSelect_RetDone:
            raise StepError(f"STEP-Datei nicht lesbar: {path}")
        reader.TransferRoots()
        shape = reader.OneShape()
        if shape.IsNull():
            raise StepError(f"STEP-Datei enthält keine Geometrie: {path}")
        return _measure(shape)
    finally:
        # OpenCascade-Speicher ausdrücklich freigeben (siehe analyze_step).
        reader = None
        shape = None
        gc.collect()


def _box_bounds(box) -> tuple:
    """Eckpunkte einer Bnd_Box - fassungsunabhängig.

    Die OpenCascade-Bindung heißt je nach Fassung anders: OCP 8.x kennt
    `GetXMin()`, das ältere OCP 7.9 (letzte Fassung für Python 3.10) nur
    `CornerMin()`/`CornerMax()`. Beides wird bedient, sonst läuft das
    Werkzeug je nach Python-Fassung des Zielrechners nicht.
    """
    if hasattr(box, "CornerMin"):
        a, b = box.CornerMin(), box.CornerMax()
        return (a.X(), a.Y(), a.Z(), b.X(), b.Y(), b.Z())
    return (box.GetXMin(), box.GetYMin(), box.GetZMin(),
            box.GetXMax(), box.GetYMax(), box.GetZMax())


def _measure(shape) -> StepGeometry:
    """Vermisst die eingelesene Gestalt (Hüllmaße, Volumen, Zylinder)."""
    from OCP.Bnd import Bnd_OBB
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    # Getrennte Volumenkörper zählen (Baugruppe vs. Einzelteil)
    from OCP.TopAbs import TopAbs_SOLID

    from OCP.Bnd import Bnd_Box

    solid_boxes = []
    sexp = TopExp_Explorer(shape, TopAbs_SOLID)
    while sexp.More():
        box = Bnd_Box()
        BRepBndLib.Add_s(sexp.Current(), box, True)
        if not box.IsVoid():
            solid_boxes.append(_box_bounds(box))
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
        # Richtung der Abweichung entscheidet über die Härte:
        #   Zeichnungsmaß GRÖSSER als das Modell -> Widerspruch, das Teil
        #   kann das Maß nicht enthalten.
        #   Modell GRÖSSER als jedes bemaßte Maß -> meist fehlt schlicht das
        #   Gesamtmaß auf dem Blatt (Maßkette, Fortsetzungsblatt). Am
        #   Kalibriersatz aus 92 echten Zeichnungen war das die Ursache für
        #   drei von vier K.O.-Fehlurteilen – deshalb nur "unsicher".
        if main > obb[0]:
            return CompareResult("passt_nicht", summary, detail, main_ok=False)
        return CompareResult(
            "unsicher", summary,
            detail + " Das Modell ist größer als jedes bemaßte Maß – "
            "möglicherweise fehlt das Gesamtmaß auf der Zeichnung.",
            main_ok=False)
    return CompareResult("unsicher", summary, detail, main_ok=main_ok)


def _check_mirrored(ctx: CheckContext, step: Path,
                     geometry: StepGeometry) -> None:
    """Prüft, ob die falsche Hand (gespiegeltes Teil) gespeichert wurde.

    Ein gespiegeltes Bauteil hat dieselben Hüllmaße, dasselbe Volumen,
    dieselbe Masse und dasselbe Bohrbild – es kommt durch jede andere
    Prüfung. Nur der Umriss in den Ansichten unterscheidet sich.
    """
    if not ctx.profile.enabled("GEO.MIRROR") or geometry.backend != "occ":
        return
    try:
        pass  # (im selben Modul)

        gerade, gespiegelt, ansichten = check_mirrored(ctx.pdf, step)
    except ImportError:
        return
    except Exception as exc:
        log.warning("Spiegelprüfung fehlgeschlagen für %s: %s", step.name, exc)
        return
    if ansichten < 2:
        return
    abstand = float(ctx.profile.rule_param("GEO.MIRROR", "min_abstand", 0.15))
    mindest = float(ctx.profile.rule_param("GEO.MIRROR", "min_score", 0.5))
    if gespiegelt >= mindest and gespiegelt - gerade >= abstand:
        ctx.add("GEO.MIRROR",
                "Die Ansichten passen besser zum GESPIEGELTEN Modell – "
                "vermutlich die falsche Ausführung (linke/rechte Hand) "
                "gespeichert",
                detail=f"Konturübereinstimmung: gespiegelt {gespiegelt:.2f} "
                       f"gegen {gerade:.2f} wie gespeichert, über "
                       f"{ansichten} Ansichten. Hüllmaße, Volumen und "
                       f"Bohrbild sind bei gespiegelten Teilen identisch – "
                       f"diese Prüfung ist die einzige, die den Fall findet. "
                       f"Vor dem Bestellen die Ausführung klären.")


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
        pass  # (im selben Modul)

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
    pass  # (im selben Modul)

    _check_mirrored(ctx, step, geometry)
    unit_error = check_unit_mismatch(ctx, geometry, dims)
    extra = [check_mass(ctx, geometry), check_hole_pattern(ctx, geometry, dims)]
    if geometry.backend == "occ" and geometry.volume:
        # Diagnose zur Massenabweichung: passt die Gewichtsangabe zu einem
        # ANDEREN Werkstoff? (kopiertes Schriftfeld, Werkstoff geändert)
        from .pruef_werkstoff import check_density_hint

        check_density_hint(ctx, geometry.volume)
    check_threads(ctx, geometry, dims)
    check_assembly_vs_part(ctx, geometry)
    from .pruef_zeichnung import check_view_vs_model

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


# ======================================================================
# contour_projection
# ======================================================================
# Ausbaustufe Geometrieabgleich: Konturprojektion STEP vs. Zeichnungsansichten.
#
# Idee: Das STEP-Modell wird aus den drei Hauptachsenrichtungen als
# 2D-Silhouette projiziert (OpenCascade HLR, sichtbare Kanten + Umrisse).
# Aus dem PDF werden die Vektorlinien extrahiert und zu Ansichten geclustert
# (Blattrahmen/Schriftfeld werden verworfen). Beide Seiten werden auf ein
# normiertes Rasterbild gezeichnet und per IoU verglichen – rotations- und
# spiegelinvariant (8 Orientierungen je Ansicht).
#
# Grenzen (bewusst): Maßhilfslinien und Schraffuren verschmutzen die
# Ansichts-Cluster, Schnittansichten entsprechen keiner Außensilhouette.
# Der Score wird deshalb nur KONSERVATIV verwendet: Ein klar guter Score kann
# ein "unsicher" des Maßabgleichs bestätigen, ein klar schlechter Score ein
# "passt" auf "unsicher" herabstufen – er erzeugt nie allein ein "passt nicht".



import gc
import logging
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


RASTER = 224          # Kantenlänge des Vergleichsrasters (Pixel)
MARGIN = 12
LINE_W = 3
DILATE = 5            # Toleranzband um Linien (MaxFilter-Kern)
MIN_VIEW_FRACTION = 0.06   # Cluster-Diagonale mind. 6 % der Seiten-Diagonale
MAX_VIEWS = 4
# Score-Schwellen (kalibriert an den Mockzeichnungen, s. tests):
# richtige Paarungen ~0.58-0.80, falsche ~0.12-0.31 -> dazwischen neutral.
SCORE_GOOD = 0.45
SCORE_BAD = 0.20

Segment = tuple[float, float, float, float]
WSegment = tuple[float, float, float, float, float]  # + Strichbreite


@dataclass
class ViewCluster:
    segments: list[Segment]        # Konturlinien (breite Striche, ISO 128)
    bbox: tuple[float, float, float, float]
    all_count: int = 0             # inkl. Maß-/Hilfslinien (nur Statistik)


@dataclass
class ContourResult:
    score: float                  # bestes Mittel der Ansichts-Scores (0..1)
    views_used: int
    per_view: list[float] = field(default_factory=list)
    detail: str = ""


# ======================================================================
# STEP-Seite: Silhouetten über HLR
# ======================================================================
def project_step_silhouettes(step_path: Path) -> list[list[Segment]]:
    """Projiziert das Modell entlang der drei OBB-Hauptachsen.

    Liefert je Richtung eine Liste von 2D-Segmenten (sichtbare Kanten und
    Umrisse). Benötigt OCP; ImportError wird nach oben gereicht.
    """
    from OCP.Bnd import Bnd_OBB
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepBndLib import BRepBndLib
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Ax3
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    reader = STEPControl_Reader()
    if reader.ReadFile(str(step_path)) != IFSelect_RetDone:
        raise ValueError(f"STEP nicht lesbar: {step_path}")
    reader.TransferRoots()
    shape = reader.OneShape()
    try:
        return _project_shape(shape)
    finally:
        # Ohne ausdrückliches Freigeben behält OpenCascade das Modell im
        # Speicher (rund 25 MB je Datei) – im Dauerlauf tödlich.
        reader = None
        shape = None
        gc.collect()


def _project_shape(shape) -> list[list[Segment]]:
    """Projiziert eine eingelesene Gestalt entlang ihrer OBB-Hauptachsen."""
    from OCP.Bnd import Bnd_OBB
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepBndLib import BRepBndLib
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection
    from OCP.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt, gp_Trsf
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    obb = Bnd_OBB()
    BRepBndLib.AddOBB_s(shape, obb, True, True, True)
    center = obb.Center()
    axes = [obb.XDirection(), obb.YDirection(), obb.ZDirection()]

    silhouettes: list[list[Segment]] = []
    for i, axis in enumerate(axes):
        direction = gp_Dir(axis.X(), axis.Y(), axis.Z())
        # Up-Vektor: eine der beiden anderen Achsen
        other = axes[(i + 1) % 3]
        up = gp_Dir(other.X(), other.Y(), other.Z())
        ax2 = gp_Ax2(gp_Pnt(center.X(), center.Y(), center.Z()), direction, up)
        projector = HLRAlgo_Projector(ax2)

        algo = HLRBRep_Algo()
        algo.Add(shape)
        algo.Projector(projector)
        algo.Update()
        algo.Hide()
        extractor = HLRBRep_HLRToShape(algo)

        segments: list[Segment] = []
        for compound in (extractor.VCompound(), extractor.OutLineVCompound()):
            if compound.IsNull():
                continue
            exp = TopExp_Explorer(compound, TopAbs_EDGE)
            while exp.More():
                edge = TopoDS.Edge(exp.Current())
                exp.Next()
                try:
                    curve = BRepAdaptor_Curve(edge)
                    disc = GCPnts_QuasiUniformDeflection(curve, 0.2)
                    if not disc.IsDone() or disc.NbPoints() < 2:
                        continue
                    pts = [disc.Value(k) for k in range(1, disc.NbPoints() + 1)]
                    for a, b in zip(pts, pts[1:]):
                        # HLR liefert Kanten bereits in Projektionskoordinaten
                        segments.append((a.X(), a.Y(), b.X(), b.Y()))
                except Exception:
                    continue
        if segments:
            silhouettes.append(segments)
    return silhouettes


# ======================================================================
# PDF-Seite: Vektorlinien -> Ansichts-Cluster
# ======================================================================
def extract_views(pdf, page: int = 0) -> list[ViewCluster]:
    """Clustert die Vektorgrafik der Seite zu Ansichten.

    Blattrahmen (Cluster, der fast die ganze Seite umspannt – Schriftfeld
    hängt daran) und Winzcluster (Symbole, Pfeile) werden verworfen.
    """
    pg = pdf.doc[page]
    W, H = pg.rect.width, pg.rect.height
    wsegments = _collect_segments(pg)
    if not wsegments:
        return []

    clusters = _cluster_segments(wsegments, cell=max(W, H) / 80.0)
    page_diag = (W * W + H * H) ** 0.5
    views: list[ViewCluster] = []
    for wsegs in clusters:
        # ISO-128-Filter: sichtbare Körperkanten sind breit gezeichnet,
        # Maß-/Hilfs-/Mittellinien schmal. Nur breite Striche bilden die
        # Kontur der Ansicht; die Bounding-Box kommt ebenfalls von ihnen.
        max_w = max(s[4] for s in wsegs)
        thick = [s[:4] for s in wsegs if s[4] >= 0.6 * max_w]
        if len(thick) < 4:
            thick = [s[:4] for s in wsegs]
        xs = [c for s in thick for c in (s[0], s[2])]
        ys = [c for s in thick for c in (s[1], s[3])]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if bw > 0.85 * W and bh > 0.85 * H:
            continue  # Blattrahmen (+ angedocktes Schriftfeld)
        if (bw * bw + bh * bh) ** 0.5 < MIN_VIEW_FRACTION * page_diag:
            continue  # zu klein für eine Ansicht
        views.append(ViewCluster(thick, bbox, all_count=len(wsegs)))
    views.sort(key=lambda v: len(v.segments), reverse=True)
    return views[:MAX_VIEWS]


def _collect_segments(pg) -> list[WSegment]:
    segments: list[WSegment] = []

    for path in pg.get_drawings():
        width = float(path.get("width") or 0.0) or 0.1

        def add(p, q):
            segments.append((p.x, p.y, q.x, q.y, width))

        for item in path["items"]:
            kind = item[0]
            if kind == "l":
                add(item[1], item[2])
            elif kind == "re":
                r = item[1]
                for a, b in ((r.tl, r.tr), (r.tr, r.br), (r.br, r.bl),
                             (r.bl, r.tl)):
                    add(a, b)
            elif kind == "qu":
                q = item[1]
                for a, b in ((q.ul, q.ur), (q.ur, q.lr), (q.lr, q.ll),
                             (q.ll, q.ul)):
                    add(a, b)
            elif kind == "c":
                # Bezier grob in 8 Sehnen zerlegen
                p0, p1, p2, p3 = item[1], item[2], item[3], item[4]
                prev = p0
                for k in range(1, 9):
                    t = k / 8.0
                    mt = 1 - t
                    x = (mt**3 * p0.x + 3 * mt**2 * t * p1.x
                         + 3 * mt * t**2 * p2.x + t**3 * p3.x)
                    y = (mt**3 * p0.y + 3 * mt**2 * t * p1.y
                         + 3 * mt * t**2 * p2.y + t**3 * p3.y)

                    class _P:  # noqa: N801 - Mini-Punkt
                        pass

                    cur = _P(); cur.x, cur.y = x, y
                    add(prev, cur)
                    prev = cur
    return segments


def _cluster_segments(segments: list[WSegment], cell: float) -> list[list[WSegment]]:
    """Union-Find über belegte Rasterzellen (8er-Nachbarschaft)."""
    parent: dict[int, int] = {}

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    cell_of: dict[tuple[int, int], int] = {}
    seg_cells: list[list[int]] = []
    for idx, (x0, y0, x1, y1, _w) in enumerate(segments):
        n = max(1, int(max(abs(x1 - x0), abs(y1 - y0)) / cell))
        ids = []
        for k in range(n + 1):
            t = k / n
            cx = int((x0 + (x1 - x0) * t) / cell)
            cy = int((y0 + (y1 - y0) * t) / cell)
            key = (cx, cy)
            if key not in cell_of:
                cid = len(parent)
                parent[cid] = cid
                cell_of[key] = cid
            ids.append(cell_of[key])
        seg_cells.append(ids)
        for a, b in zip(ids, ids[1:]):
            union(a, b)
    # Nachbarzellen verschmelzen
    for (cx, cy), cid in list(cell_of.items()):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nb = cell_of.get((cx + dx, cy + dy))
                if nb is not None:
                    union(cid, nb)

    groups: dict[int, list[WSegment]] = {}
    for seg, ids in zip(segments, seg_cells):
        groups.setdefault(find(ids[0]), []).append(seg)
    return list(groups.values())


# ======================================================================
# Vergleich: normiertes Raster + IoU
# ======================================================================
def rasterize(segments: list[Segment]) -> Image.Image:
    xs = [c for s in segments for c in (s[0], s[2])]
    ys = [c for s in segments for c in (s[1], s[3])]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    span = max(x1 - x0, y1 - y0) or 1.0
    scale = (RASTER - 2 * MARGIN) / span
    img = Image.new("L", (RASTER, RASTER), 0)
    draw = ImageDraw.Draw(img)
    for sx0, sy0, sx1, sy1 in segments:
        draw.line(
            [(MARGIN + (sx0 - x0) * scale, MARGIN + (sy0 - y0) * scale),
             (MARGIN + (sx1 - x0) * scale, MARGIN + (sy1 - y0) * scale)],
            fill=255, width=LINE_W)
    return img.filter(ImageFilter.MaxFilter(DILATE))


def iou(a: Image.Image, b: Image.Image) -> float:
    pa, pb = a.tobytes(), b.tobytes()
    inter = on_a = on_b = 0
    for xa, xb in zip(pa, pb):
        va, vb = xa > 0, xb > 0
        on_a += va
        on_b += vb
        inter += va and vb
    union = on_a + on_b - inter
    return inter / union if union else 0.0


def _orientations(img: Image.Image, mirrored: bool | None = None):
    """Lagevarianten einer Ansicht.

    mirrored=None: alle (Drehungen und Spiegelungen)
    mirrored=False: nur Drehungen  – passt zum Modell wie gespeichert
    mirrored=True: nur Spiegelungen – passt zur gespiegelten Ausführung
    """
    if mirrored is not True:
        yield img
        yield img.transpose(Image.ROTATE_90)
        yield img.transpose(Image.ROTATE_180)
        yield img.transpose(Image.ROTATE_270)
    if mirrored is not False:
        m = img.transpose(Image.FLIP_LEFT_RIGHT)
        yield m
        yield m.transpose(Image.ROTATE_90)
        yield m.transpose(Image.ROTATE_180)
        yield m.transpose(Image.ROTATE_270)


def match_views(views: list[ViewCluster],
                silhouettes: list[list[Segment]],
                mirrored: bool | None = None) -> ContourResult:
    if not views or not silhouettes:
        return ContourResult(0.0, 0, detail="keine Ansichten/Silhouetten")
    sil_imgs = [rasterize(s) for s in silhouettes]
    per_view: list[float] = []
    for view in views:
        vimg = rasterize(view.segments)
        best = 0.0
        for oriented in _orientations(vimg, mirrored):
            for simg in sil_imgs:
                best = max(best, iou(oriented, simg))
        per_view.append(round(best, 3))
    per_view.sort(reverse=True)
    top = per_view[:2]
    score = sum(top) / len(top)
    return ContourResult(
        score=round(score, 3), views_used=len(views), per_view=per_view,
        detail=f"Ansichts-Scores: {per_view} gegen {len(silhouettes)} "
               f"Silhouetten")


def compare_contours(pdf, step_path: Path) -> ContourResult:
    """Kompletter Konturabgleich Zeichnung (Seite 0) gegen STEP."""
    silhouettes = project_step_silhouettes(step_path)
    views = extract_views(pdf)
    return match_views(views, silhouettes)


def check_mirrored(pdf, step_path: Path) -> tuple[float, float, int]:
    """Passt die Zeichnung besser zur GESPIEGELTEN Ausführung?

    Der klassische Fall „falsche Hand gespeichert": Hüllmaße, Volumen,
    Masse und Bohrbild sind bei einem gespiegelten Teil identisch – alle
    anderen Prüfungen laufen also durch. Nur die Kontur verrät es.

    Liefert (Score gerade, Score gespiegelt, Anzahl Ansichten). Verglichen
    wird dieselbe Silhouette einmal nur mit Drehungen und einmal nur mit
    Spiegelungen; das ist gleichwertig dazu, das Modell selbst zu spiegeln,
    aber ohne zweite HLR-Projektion.
    """
    silhouettes = project_step_silhouettes(step_path)
    views = extract_views(pdf)
    if not views or not silhouettes:
        return (0.0, 0.0, 0)
    gerade = match_views(views, silhouettes, mirrored=False)
    gespiegelt = match_views(views, silhouettes, mirrored=True)
    return (gerade.score, gespiegelt.score, len(views))
