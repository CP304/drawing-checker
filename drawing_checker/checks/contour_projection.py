"""Ausbaustufe Geometrieabgleich: Konturprojektion STEP vs. Zeichnungsansichten.

Idee: Das STEP-Modell wird aus den drei Hauptachsenrichtungen als
2D-Silhouette projiziert (OpenCascade HLR, sichtbare Kanten + Umrisse).
Aus dem PDF werden die Vektorlinien extrahiert und zu Ansichten geclustert
(Blattrahmen/Schriftfeld werden verworfen). Beide Seiten werden auf ein
normiertes Rasterbild gezeichnet und per IoU verglichen – rotations- und
spiegelinvariant (8 Orientierungen je Ansicht).

Grenzen (bewusst): Maßhilfslinien und Schraffuren verschmutzen die
Ansichts-Cluster, Schnittansichten entsprechen keiner Außensilhouette.
Der Score wird deshalb nur KONSERVATIV verwendet: Ein klar guter Score kann
ein "unsicher" des Maßabgleichs bestätigen, ein klar schlechter Score ein
"passt" auf "unsicher" herabstufen – er erzeugt nie allein ein "passt nicht".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

log = logging.getLogger(__name__)

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


def _orientations(img: Image.Image):
    yield img
    yield img.transpose(Image.ROTATE_90)
    yield img.transpose(Image.ROTATE_180)
    yield img.transpose(Image.ROTATE_270)
    m = img.transpose(Image.FLIP_LEFT_RIGHT)
    yield m
    yield m.transpose(Image.ROTATE_90)
    yield m.transpose(Image.ROTATE_180)
    yield m.transpose(Image.ROTATE_270)


def match_views(views: list[ViewCluster],
                silhouettes: list[list[Segment]]) -> ContourResult:
    if not views or not silhouettes:
        return ContourResult(0.0, 0, detail="keine Ansichten/Silhouetten")
    sil_imgs = [rasterize(s) for s in silhouettes]
    per_view: list[float] = []
    for view in views:
        vimg = rasterize(view.segments)
        best = 0.0
        for oriented in _orientations(vimg):
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
