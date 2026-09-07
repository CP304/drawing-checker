"""Testdaten: Mockpakete bauen, Kalibrierzeichnungen holen, Fehler einbauen.

    python -m mockdata bauen [ziel]              Mockpakete nach mockdata/out
    python -m mockdata quellen                   Kalibrierzeichnungen auspacken
    python -m mockdata fehler <quelle> <ziel>    Referenz- und Fehlerpakete

Die 84 echten Kalibrierzeichnungen liegen als EIN Archiv im Repository
(mockdata/echt_quellen.zip). `quellen` packt sie nach mockdata/.echt_quellen
aus - die anderen Unterbefehle tun das bei Bedarf von selbst.
"""
from __future__ import annotations

# ======================================================================
# quellen
# ======================================================================
# Zugriff auf die echten Kalibrierzeichnungen.
#
# Die 84 Fremdzeichnungen (plus STEP-Modelle) liegen als EIN Archiv im
# Repository – `mockdata/echt_quellen.zip`. Grund: Als Einzeldateien waren
# es über hundert Einträge, die jede Dateiliste zumüllen und beim
# Weitergeben stören. Wer sie braucht, bekommt sie hier ausgepackt; das
# Auspacken passiert einmalig in einen Cache-Ordner, der nicht im
# Repository liegt.
#
#     from mockdata.daten import zeichnungen
#
#     ordner = zeichnungen()      # Path auf den ausgepackten Ordner
#
# Herkunft und Lizenzen: mockdata/echt_quellen/SOURCES.md
import zipfile
from pathlib import Path

HIER = Path(__file__).resolve().parent
ARCHIV = HIER / "echt_quellen.zip"
CACHE = HIER / ".echt_quellen"          # in .gitignore


def zeichnungen(ziel: Path | None = None, neu: bool = False) -> Path:
    """Packt die Kalibrierzeichnungen aus und liefert den Ordner.

    Beim zweiten Aufruf wird nichts noch einmal ausgepackt, außer mit
    `neu=True`. Fehlt das Archiv, wird ein sprechender Fehler geworfen –
    ohne die Zeichnungen ist eine Kalibrierung sinnlos.
    """
    ordner = ziel or CACHE
    if not ARCHIV.is_file():
        raise FileNotFoundError(
            f"Kalibrierzeichnungen fehlen: {ARCHIV} nicht gefunden. "
            f"Sie liegen als ZIP im Repository (mockdata/echt_quellen.zip).")
    fertig = ordner / ".ausgepackt"
    if neu or not fertig.exists():
        ordner.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(ARCHIV) as zf:
            zf.extractall(ordner)
        fertig.write_text(str(ARCHIV.stat().st_mtime_ns), encoding="ascii")
    return ordner


def anzahl() -> tuple[int, int]:
    """(Zeichnungen, STEP-Modelle) im Archiv – ohne es auszupacken."""
    with zipfile.ZipFile(ARCHIV) as zf:
        namen = zf.namelist()
    pdfs = sum(1 for n in namen if n.lower().endswith(".pdf"))
    steps = sum(1 for n in namen if n.lower().endswith((".step", ".stp")))
    return pdfs, steps


# ======================================================================
# generate
# ======================================================================
# Erzeugt realistische Mock-YMATDOCS-Pakete für Entwicklung und Tests.
#
# Je Materialnummer entsteht ein ZIP wie aus YMATDOCS (PDF + ggf. STEP + native
# Dummy-Datei) sowie eine Input-Excel wie vom Anwender hochgeladen.
#
# Die Zeichnungen sind vektorbasiert (A3, Rahmen, Schriftfeld nach ISO 7200,
# mehrere Ansichten, Maßketten, Symbolik) und enthalten gezielt eingebaute
# Fehler:
#
#   10473215  Schweißkonsole   – Werkstoff 1.4305 trotz Schweißnähten,
#                                deutsche Anmerkungen, ISO 5817 ohne Gruppe;
#                                STEP passt (inkl. Bohrbild 4x18 und Masse).
#   10473216  Gussgehäuse      – keine Allgemeintoleranz, Projektionsmethode
#                                fehlt; STEP ist die FALSCHE Konfiguration
#                                (kürzeres Gehäuse) -> Geometrie-K.O., zusätzlich
#                                Massenabweichung als unabhängiges Indiz.
#   10473217  Antriebswelle    – sauber zweisprachig, vollständig; STEP passt.
#   10473218  Antriebswelle    – nur gescannt (kein Textlayer), kein STEP.
#
# Aufruf:  python -m mockdata bauen [zielordner]   (Default: mockdata/out)
import io
import sys
import zipfile
from pathlib import Path

import pymupdf

MM = 1190.55 / 420.0  # A3 quer: pt je mm
PAGE_W, PAGE_H = 1190.55, 841.89
THIN, THICK = 0.5, 1.4
BLACK = (0, 0, 0)

# Schrift mit vollem Symbolvorrat (⌀, ↗, ⌖ …); Helvetica kennt diese nicht.
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
_FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _find_font(cands: list[str]) -> str | None:
    for c in cands:
        if Path(c).exists():
            return c
    return None


def mm(v: float) -> float:
    return v * MM


class Sheet:
    """A3-Zeichnungsblatt mit Rahmen und ISO-7200-Schriftfeld."""

    def __init__(self):
        self.doc = pymupdf.open()
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self.shape = self.page.new_shape()
        self._font = _find_font(_FONT_CANDIDATES)
        self._font_bold = _find_font(_FONT_BOLD_CANDIDATES)
        if self._font:
            self.page.insert_font(fontname="F0", fontfile=self._font)
        if self._font_bold:
            self.page.insert_font(fontname="F1", fontfile=self._font_bold)

    # ------------------------------------------------------------ Grafik
    def line(self, x0, y0, x1, y1, width=THIN):
        self.shape.draw_line((mm(x0), mm(y0)), (mm(x1), mm(y1)))
        self.shape.finish(width=width, color=BLACK)

    def rect(self, x0, y0, x1, y1, width=THIN):
        self.shape.draw_rect(pymupdf.Rect(mm(x0), mm(y0), mm(x1), mm(y1)))
        self.shape.finish(width=width, color=BLACK)

    def circle(self, cx, cy, r, width=THIN, dashes=None):
        self.shape.draw_circle((mm(cx), mm(cy)), mm(r))
        self.shape.finish(width=width, color=BLACK, dashes=dashes)

    def dashed_line(self, x0, y0, x1, y1, pattern="[3 2] 0"):
        self.shape.draw_line((mm(x0), mm(y0)), (mm(x1), mm(y1)))
        self.shape.finish(width=THIN, color=BLACK, dashes=pattern)

    def text(self, x, y, s, size=8, bold=False):
        if bold:
            fname = "F1" if self._font_bold else "hebo"
        else:
            fname = "F0" if self._font else "helv"
        self.page.insert_text((mm(x), mm(y)), s, fontsize=size,
                              fontname=fname, color=BLACK)

    def arrow(self, x, y, direction):
        """Massstabspfeil (gefülltes Dreieck), direction: 'l','r','u','d'."""
        s = 1.2
        pts = {
            "r": [(x, y), (x - 2.5 * s, y - s * 0.7), (x - 2.5 * s, y + s * 0.7)],
            "l": [(x, y), (x + 2.5 * s, y - s * 0.7), (x + 2.5 * s, y + s * 0.7)],
            "d": [(x, y), (x - s * 0.7, y - 2.5 * s), (x + s * 0.7, y - 2.5 * s)],
            "u": [(x, y), (x - s * 0.7, y + 2.5 * s), (x + s * 0.7, y + 2.5 * s)],
        }[direction]
        self.shape.draw_polyline([(mm(a), mm(b)) for a, b in pts + [pts[0]]])
        self.shape.finish(color=BLACK, fill=BLACK, width=0.3)

    # -------------------------------------------------------- Bemaßung
    def dim_h(self, x0, x1, y_ref, y_dim, label, size=8):
        """Horizontale Maßkette zwischen x0..x1, Maßlinie auf y_dim."""
        for x in (x0, x1):
            self.line(x, y_ref, x, y_dim + (1 if y_dim > y_ref else -1))
        self.line(x0, y_dim, x1, y_dim)
        self.arrow(x0, y_dim, "l")
        self.arrow(x1, y_dim, "r")
        w = len(label) * size * 0.22
        self.text((x0 + x1) / 2 - w / 2, y_dim - 1.2, label, size=size)

    def dim_v(self, y0, y1, x_ref, x_dim, label, size=8):
        for y in (y0, y1):
            self.line(x_ref, y, x_dim + (1 if x_dim > x_ref else -1), y)
        self.line(x_dim, y0, x_dim, y1)
        self.arrow(x_dim, y0, "u")
        self.arrow(x_dim, y1, "d")
        self.text(x_dim + 1.2, (y0 + y1) / 2 + 1.0, label, size=size)

    def leader(self, x0, y0, x1, y1, label, size=8):
        self.line(x0, y0, x1, y1)
        self.line(x1, y1, x1 + 6, y1)
        self.arrow(x0, y0, "l" if x1 > x0 else "r")
        self.text(x1 + 7, y1 + 1.0, label, size=size)

    # ---------------------------------------------------- Blattrahmen
    def frame(self):
        self.rect(5, 5, 415, 292, THICK)
        self.rect(10, 10, 410, 287, THIN)
        for i, x in enumerate(range(10, 411, 50)):
            if i:
                self.line(x, 5, x, 10)
                self.line(x, 287, x, 292)
            self.text(x + 22, 8.7, str(i + 1), size=6)
        for i, ch in enumerate("ABCDEF"):
            y = 10 + i * 46.2
            if i:
                self.line(5, y, 10, y)
                self.line(410, y, 415, y)
            self.text(6.5, y + 25, ch, size=6)

    def title_block(self, *, drawno, title_de, title_en, material, weight,
                    scale="1:2", bilingual=True, projection_text=True):
        x0, y0, x1, y1 = 250, 232, 410, 287
        self.rect(x0, y0, x1, y1, THICK)
        rows = [y0 + 11, y0 + 22, y0 + 33, y0 + 44]
        for y in rows:
            self.line(x0, y, x1, y)
        self.line(x0 + 55, y0, x0 + 55, rows[2])
        self.line(x0 + 105, y0, x0 + 105, rows[2])

        def cell(x, y, label_de, label_en, value):
            lbl = f"{label_de} / {label_en}" if bilingual else label_de
            self.text(x + 1.5, y + 3.4, lbl, size=5)
            self.text(x + 1.5, y + 9.2, value, size=8, bold=True)

        cell(x0, y0, "Werkstoff", "Material", material)
        cell(x0 + 55, y0, "Maßstab", "Scale", scale)
        cell(x0 + 105, y0, "Gewicht", "Weight", weight)
        cell(x0, rows[0], "Erstellt", "Drawn", "chp  2025-11-14")
        cell(x0 + 55, rows[0], "Geprüft", "Checked", "mwe  2025-11-20")
        cell(x0 + 105, rows[0], "Freigegeben", "Approved", "kfr  2025-11-21")
        cell(x0, rows[1], "Änderung", "Revision", "B")
        cell(x0 + 55, rows[1], "Datum", "Date", "2026-01-12")
        cell(x0 + 105, rows[1], "Blatt", "Sheet", "1/1")
        self.text(x0 + 1.5, rows[2] + 3.4,
                  "Benennung / Title" if bilingual else "Benennung", size=5)
        self.text(x0 + 1.5, rows[2] + 8.6, title_de, size=9, bold=True)
        if bilingual:
            self.text(x0 + 90, rows[2] + 8.6, title_en, size=8)
        self.text(x0 + 1.5, rows[3] + 3.4,
                  "Zeichnungsnummer / Drawing no." if bilingual
                  else "Zeichnungsnummer", size=5)
        self.text(x0 + 1.5, rows[3] + 9.4, drawno, size=11, bold=True)
        self.text(x0 + 105, rows[3] + 9.4, "MUSTER AG", size=8, bold=True)
        if projection_text:
            self._projection_symbol(x0 - 28, y1 - 14)
            self.text(x0 - 34, y1 - 17, "Projektionsmethode 1 / First angle",
                      size=5)

    def _projection_symbol(self, x, y):
        # Kegelstumpf-Symbol (vereinfachte Grafik) + Ansicht daneben
        self.line(x, y - 4, x + 10, y - 6)
        self.line(x, y + 4, x + 10, y + 6)
        self.line(x, y - 4, x, y + 4)
        self.line(x + 10, y - 6, x + 10, y + 6)
        self.circle(x + 18, y, 4)
        self.circle(x + 18, y, 2.2)

    def notes(self, x, y, lines, size=7):
        for i, line in enumerate(lines):
            self.text(x, y + i * 4.6, line, size=size)

    def save(self, path: Path):
        self.shape.commit()
        self.doc.save(path, deflate=True)
        self.doc.close()


# ===================================================================== Teile
def draw_weld_bracket(path: Path):
    """Schweißkonsole: Grundplatte + Steg + Rippe. Seeded Fehler:
    Werkstoff 1.4305 (Automaten-Edelstahl, NICHT schweißgeeignet) trotz
    Schweißsymbolik + "feuerverzinkt" auf Edelstahl (fachliche Widersprüche),
    deutsche Anmerkungen, ISO 5817 ohne Bewertungsgruppe, ISO 13715 fehlt."""
    s = Sheet()
    s.frame()

    # Vorderansicht (Grundplatte 320x25, Steg 180 hoch, Rippe)
    ox, oy = 45, 175  # Ursprung unten links der Ansicht (in mm auf dem Blatt)
    sc = 0.4          # entspricht exakt dem Schriftfeld-Maßstab 1:2,5
    def X(v): return ox + v * sc
    def Y(v): return oy - v * sc
    # Grundplatte
    s.rect(X(0), Y(25), X(320), Y(0), THICK)
    # Steg mittig, Dicke 20
    s.rect(X(150), Y(205), X(170), Y(25), THICK)
    # Rippe als Dreieck
    s.shape.draw_polyline([
        (mm(X(170)), mm(Y(25))), (mm(X(260)), mm(Y(25))),
        (mm(X(170)), mm(Y(140))), (mm(X(170)), mm(Y(25)))])
    s.shape.finish(width=THICK, color=BLACK)
    # Bohrungen in Grundplatte (Seitenansicht: Mittellinien)
    for bx in (40, 280):
        s.dashed_line(X(bx), Y(-8), X(bx), Y(33))
    # Kopfbohrung im Steg
    s.circle(X(160), Y(180), 8 * sc, THICK)
    s.dashed_line(X(160) - 8, Y(180), X(160) + 8, Y(180))
    s.dashed_line(X(160), Y(180) - 8 / sc * sc, X(160), Y(180) + 8)

    # Bemaßung Vorderansicht
    s.dim_h(X(0), X(320), Y(0), Y(0) + 14, "320")
    s.dim_h(X(0), X(150), Y(25), Y(25) - 46, "150")
    s.dim_v(Y(205), Y(0), X(320), X(320) + 14, "205")
    s.dim_v(Y(25), Y(0), X(320), X(320) + 26, "25")
    s.leader(X(162), Y(183), X(200), Y(230), "⌀16 H11")
    # Schweißsymbol als Leader (vereinfachter Text)
    s.leader(X(152), Y(35), X(95), Y(80), "a5 △ beidseitig")

    # Draufsicht
    oy2 = 262
    def Y2(v): return oy2 - v * sc
    s.rect(X(0), Y2(120), X(320), Y2(0), THICK)
    for bx in (40, 280):
        for by in (30, 90):
            s.circle(X(bx), Y2(by), 9 * sc, THICK)
            s.dashed_line(X(bx) - 6, Y2(by), X(bx) + 6, Y2(by))
            s.dashed_line(X(bx), Y2(by) - 6, X(bx), Y2(by) + 6)
    s.rect(X(150), Y2(120), X(170), Y2(0), THIN)
    s.dim_h(X(0), X(40), Y2(0), Y2(0) + 12, "40")
    s.dim_h(X(40), X(280), Y2(0), Y2(0) + 12, "240")
    s.dim_v(Y2(120), Y2(0), X(320), X(320) + 14, "120")
    s.dim_v(Y2(90), Y2(30), X(320), X(320) + 26, "60")
    s.leader(X(282), Y2(92), X(315), Y2(115), "4×⌀18")
    s.text(X(120), Y2(130), "Draufsicht", size=7)
    s.text(X(120), 90, "Vorderansicht", size=7)

    # Anmerkungen: bewusst NUR deutsch + ISO 5817 ohne Gruppe (Fehler!)
    s.notes(255, 180, [
        "Anmerkungen:",
        "1. Alle Schweißnähte umlaufend, a5, nicht bemaßte Nähte a4.",
        "2. Schweißnahtgüte nach ISO 5817.",
        "3. Nach dem Schweißen spannungsarm glühen.",
        "4. Konsole komplett feuerverzinkt nach Absprache.",
        "5. Unbemaßte Radien R3.",
    ])
    s.notes(255, 215, [
        "Allgemeintoleranzen ISO 2768-mK",
        "Maße in mm / Dimensions in mm",
        "Ra 12,5, Bohrungen Ra 6,3",
    ])
    s.title_block(
        drawno="DRW-10473215-B", title_de="Schweißkonsole",
        title_en="Welded bracket", material="1.4305",
        weight="10,6 kg", scale="1:2.5")
    s.text(15, 15, "10473215", size=9, bold=True)
    s.save(path)


def draw_cast_housing(path: Path, drawno="DRW-10473216-A"):
    """Gussgehäuse. Seeded Fehler: KEINE Allgemeintoleranz, KEINE
    Projektionsmethode, keine Gusstoleranz (ISO 8062 fehlt)."""
    s = Sheet()
    s.frame()

    ox, oy = 40, 190
    sc = 0.4          # entspricht exakt dem Schriftfeld-Maßstab 1:2,5
    def X(v): return ox + v * sc
    def Y(v): return oy - v * sc
    # Gehäusekörper 280 x 180 mit Flanschfüßen
    s.rect(X(0), Y(180), X(280), Y(0), THICK)
    s.rect(X(-25), Y(22), X(0), Y(0), THICK)
    s.rect(X(280), Y(22), X(305), Y(0), THICK)
    # Lagerbohrung zentrisch ⌀90, Deckelbund ⌀140
    cx, cy = X(140), Y(100)
    s.circle(cx, cy, 45 * sc, THICK)
    s.circle(cx, cy, 70 * sc, THIN)
    s.dashed_line(cx - 35, cy, cx + 35, cy)
    s.dashed_line(cx, cy - 35, cx, cy + 35)
    # Verschraubungslochkreis ⌀170, 6 Bohrungen ⌀13 (nur 4 gezeichnet)
    s.circle(cx, cy, 85 * sc, width=THIN, dashes="[2 2] 0")
    for ang_deg in (0, 90, 180, 270):
        import math
        bx = cx + 85 * sc * math.cos(math.radians(ang_deg))
        by = cy + 85 * sc * math.sin(math.radians(ang_deg))
        s.circle(bx, by, 6.5 * sc, THIN)

    s.dim_h(X(0), X(280), Y(0), Y(0) + 14, "280 ±0,8")
    s.dim_h(X(-25), X(305), Y(0), Y(0) + 26, "330")
    s.dim_v(Y(180), Y(0), X(305), X(305) + 14, "180")
    s.dim_v(Y(100), Y(0), X(-25), X(-25) - 14, "100")
    s.leader(cx + 14, cy - 14, X(240), Y(160), "⌀90 H7")
    s.leader(cx + 24, cy + 20, X(250), Y(40), "⌀140")
    s.leader(cx - 30, cy - 30, X(30), Y(165), "6×⌀13 auf ⌀170")

    # Seitenansicht (Tiefe 120)
    ox2 = 250
    def X2(v): return ox2 + v * sc
    s.rect(X2(0), Y(180), X2(120), Y(0), THICK)
    s.rect(X2(120), Y(140), X2(150), Y(60), THICK)  # Anschlussstutzen
    s.dim_h(X2(0), X2(120), Y(0), Y(0) + 14, "120")
    s.dim_h(X2(120), X2(150), Y(60), Y(60) - 10, "30")
    s.leader(X2(135), Y(100), X2(160), Y(120), "G1½\"")

    # Anmerkungen zweisprachig, aber ohne Allgemeintoleranz/Gusstoleranz!
    s.notes(30, 240, [
        "Notes / Anmerkungen:",
        "1. Casting material EN-GJS-400-15 / Gussteil EN-GJS-400-15.",
        "2. Machined surfaces Ra 6,3 / bearbeitete Flächen Ra 6,3.",
        "3. Pressure test 6 bar / Druckprüfung 6 bar.",
        "4. Paint RAL 7016 / Lackierung RAL 7016.",
    ])
    s.notes(30, 264, ["◎ ⌀0,3 A   Lagerbohrung zu Fußfläche / bearing bore to base",
                      "Bezug A = Fußfläche / datum A = base face"])
    s.title_block(
        drawno=drawno, title_de="Gussgehäuse",
        title_en="Cast housing", material="EN-GJS-400-15",
        weight="31,2 kg", scale="1:2.5", projection_text=False)
    s.text(15, 15, "10473216", size=9, bold=True)
    s.save(path)


def draw_shaft(path: Path):
    """Antriebswelle: vollständige, zweisprachige Zeichnung (Soll: grün)."""
    s = Sheet()
    s.frame()

    ox, oy = 50, 140
    sc = 0.5          # entspricht exakt dem Schriftfeld-Maßstab 1:2
    def X(v): return ox + v * sc
    def Y(v): return oy - v * sc
    # Wellenkontur (halbe Darstellung gespiegelt): Absätze
    # Abschnitte: ⌀40x80 | ⌀55x120 | ⌀70x60 | ⌀55x90 | ⌀45x70   Gesamt 420
    steps = [(40, 80), (55, 120), (70, 60), (55, 90), (45, 70)]
    x = 0.0
    for dia, ln in steps:
        r = dia / 2
        s.rect(X(x), Y(r) - (0), X(x + ln), Y(-r), THICK)
        x += ln
    total = x
    s.dashed_line(X(-10), Y(0), X(total + 10), Y(0))  # Mittellinie
    # Fasen andeuten
    s.line(X(0), Y(20 - 2), X(2), Y(20))
    s.line(X(total), Y(22.5 - 2), X(total - 2), Y(22.5))

    # Passfedernut im ⌀55-Abschnitt
    s.rect(X(210), Y(8), X(270), Y(-8), THIN)

    # Bemaßung
    y0 = Y(-40)
    s.dim_h(X(0), X(80), Y(-35), y0, "80")
    s.dim_h(X(80), X(200), Y(-35), y0, "120")
    s.dim_h(X(200), X(260), Y(-35), y0, "60")
    s.dim_h(X(260), X(350), Y(-35), y0, "90")
    s.dim_h(X(350), X(420), Y(-35), y0, "70")
    s.dim_h(X(0), X(420), Y(-35), Y(-52), "420 ±0,2")
    s.leader(X(40), Y(20), X(20), Y(55), "⌀40 k6 (E)")
    s.leader(X(140), Y(27.5), X(120), Y(62), "⌀55 h6 (E)")
    s.leader(X(230), Y(35), X(215), Y(68), "⌀70")
    s.leader(X(300), Y(27.5), X(330), Y(62), "⌀55 h6 (E)")
    s.leader(X(390), Y(22.5), X(400), Y(55), "⌀45 k6 (E)")
    s.leader(X(240), Y(8), X(280), Y(30), "Passfeder 16×10 / key 16×10")

    # Detailansicht Nut
    s.text(60, 200, "Detail Nut / detail keyway  M 1:1", size=7)
    s.rect(60, 205, 120, 235, THIN)
    s.rect(75, 212, 105, 228, THICK)
    s.dim_h(75, 105, 228, 242, "60")
    s.dim_v(212, 228, 105, 112, "16 P9")

    # GD&T: Rundlauf
    s.notes(250, 195, [
        "↗ 0,05 A–B   Lagersitze / bearing seats",
        "Bezüge A, B = Zentrierbohrungen / datums A, B = centre holes",
        "Zentrierbohrungen DIN 332-D M8 beidseitig / both ends",
    ])
    s.notes(30, 250, [
        "Allgemeintoleranzen / General tolerances: ISO 2768-fH",
        "Tolerierung nach / Tolerancing per ISO 8015",
        "Hüllbedingung (E) an Lagersitzen / envelope requirement on seats",
        "Kanten / Edges: ISO 13715 -0,3",
        "Oberfläche / Surface: Ra 1,6, Lagersitze / bearing seats Ra 0,8",
        "Maße in mm / Dimensions in mm",
        "Wärmebehandlung / Heat treatment: vergütet +QT / quenched and tempered",
    ])
    s.title_block(
        drawno="DRW-10473217-C", title_de="Antriebswelle",
        title_en="Drive shaft", material="42CrMo4 +QT",
        weight="7,4 kg", scale="1:2")
    s.text(15, 15, "10473217", size=9, bold=True)
    s.save(path)


# ---------------------------------------------------------------- STEP-Teile
def _export_step(shape, path: Path):
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer

    writer = STEPControl_Writer()
    Interface_Static.SetCVal_s("write.step.schema", "AP214")
    writer.Transfer(shape, STEPControl_AsIs)
    if writer.Write(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"STEP-Export fehlgeschlagen: {path}")


def make_step_bracket(path: Path):
    """Schweißkonsole passend zur Zeichnung (320 × 120 × 205).

    Inklusive des Bohrbilds der Zeichnung: 4×⌀18 in der Grundplatte und
    die Kopfbohrung ⌀16 im Steg – damit prüft der Bohrbildabgleich echt.
    (⌀16 statt ⌀22, weil eine größere Bohrung den 20 mm breiten Steg
    durchtrennen würde – genau das meldet GEO.ASSEMBLY.)
    """
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    base = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 320, 120, 25).Shape()
    web = BRepPrimAPI_MakeBox(gp_Pnt(150, 0, 25), 20, 120, 180).Shape()
    shape = BRepAlgoAPI_Fuse(base, web).Shape()
    # 4×⌀18 Befestigungsbohrungen (Raster 240 × 60)
    for bx in (40, 280):
        for by in (30, 90):
            hole = BRepPrimAPI_MakeCylinder(
                gp_Ax2(gp_Pnt(bx, by, -1), gp_Dir(0, 0, 1)), 9.0, 27).Shape()
            shape = BRepAlgoAPI_Cut(shape, hole).Shape()
    # Kopfbohrung ⌀22 quer durch den Steg
    head = BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(160, -1, 180), gp_Dir(0, 1, 0)), 8.0, 122).Shape()
    shape = BRepAlgoAPI_Cut(shape, head).Shape()
    _export_step(shape, path)


def make_step_housing_wrong(path: Path):
    """FALSCHE Konfiguration: Gehäuse nur 200 lang statt 280 (und flacher)."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    body = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 200, 120, 140).Shape()
    bore = BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(100, -1, 70), gp_Dir(0, 1, 0)), 32.5, 122).Shape()
    shape = BRepAlgoAPI_Cut(body, bore).Shape()
    _export_step(shape, path)


def make_step_shaft(path: Path):
    """Antriebswelle passend zur Zeichnung (Absätze, Gesamtlänge 420)."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    steps = [(40, 80), (55, 120), (70, 60), (55, 90), (45, 70)]
    shape = None
    z = 0.0
    for dia, ln in steps:
        cyl = BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(0, 0, z), gp_Dir(0, 0, 1)), dia / 2, ln).Shape()
        shape = cyl if shape is None else BRepAlgoAPI_Fuse(shape, cyl).Shape()
        z += ln
    _export_step(shape, path)


# ------------------------------------------------------------ Scan-Variante
def rasterize_pdf(src: Path, dst: Path, dpi: int = 150):
    """Erzeugt eine Bild-PDF (wie ein Scan, ohne Textlayer)."""
    with pymupdf.open(src) as doc:
        out = pymupdf.open()
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            p = out.new_page(width=page.rect.width, height=page.rect.height)
            p.insert_image(p.rect, stream=pix.tobytes("png"))
        out.save(dst)
        out.close()


# --------------------------------------------------------------------- Excel
def make_input_excel(path: Path, materials: list[tuple[str, str]]):
    import openpyxl
    from openpyxl.styles import Font

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Materialliste"
    headers = ["Lfd.Nr.", "Werk", "Materialnummer", "Benennung", "Disponent",
               "Bemerkung"]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
    for i, (matnr, name) in enumerate(materials, start=1):
        ws.append([i, "1000", matnr, name, "EK-4711", ""])
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 28
    wb.save(path)


# ---------------------------------------------------------------------- Main
def build_all(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "_arbeit"
    work.mkdir(exist_ok=True)

    plans = {
        "10473215": ("Schweißkonsole", draw_weld_bracket, make_step_bracket),
        "10473216": ("Gussgehäuse", draw_cast_housing, make_step_housing_wrong),
        "10473217": ("Antriebswelle", draw_shaft, make_step_shaft),
    }
    materials: list[tuple[str, str]] = []
    for matnr, (name, draw_fn, step_fn) in plans.items():
        pdf = work / f"Z_{matnr}.pdf"
        stp = work / f"M_{matnr}.stp"
        draw_fn(pdf)
        try:
            step_fn(stp)
        except ImportError:
            stp = None
        with zipfile.ZipFile(out_dir / f"{matnr}.zip", "w",
                             zipfile.ZIP_DEFLATED) as zf:
            zf.write(pdf, pdf.name)
            if stp:
                zf.write(stp, stp.name)
            zf.writestr(f"N_{matnr}.CATPart", b"native cad dummy")
        materials.append((matnr, name))

    # 10473218: Scan der Welle, kein STEP
    scan_src = work / "Z_10473217.pdf"
    scan_pdf = work / "Z_10473218_scan.pdf"
    rasterize_pdf(scan_src, scan_pdf)
    with zipfile.ZipFile(out_dir / "10473218.zip", "w") as zf:
        zf.write(scan_pdf, scan_pdf.name)
    materials.append(("10473218", "Antriebswelle (Scan)"))

    # 10473219 steht in der Excel, hat aber KEIN Paket (Not-Found-Pfad)
    materials.append(("10473219", "Distanzhülse (kein Paket)"))

    excel = out_dir / "Materialliste_Mock.xlsx"
    make_input_excel(excel, materials)
    print(f"Mockdaten erzeugt in {out_dir}")
    return excel


# ======================================================================
# inject_errors
# ======================================================================
# Baut aus ECHTEN Zeichnungen alter Prüfungen Mock-Pakete mit eingebauten Fehlern.
#
# Gedacht für die Kalibrierung des Checkers an realen Daten: einen Ordner mit
# echten PDFs (und optional passenden STEP-Dateien) hineingeben, das Skript
# erzeugt je Zeichnung YMATDOCS-artige ZIPs – einmal unverändert (Referenz)
# und einmal mit gezielt injizierten Fehlern – plus Input-Excel und ein
# Manifest, das dokumentiert, welcher Fehler wo eingebaut wurde.
#
# Aufruf:
#     python -m mockdata fehler QUELLORDNER ZIELORDNER
#
# Konventionen im Quellordner:
#     <name>.pdf            die Zeichnung (Pflicht)
#     <name>.stp/.step      zugehöriges STEP (optional)
#
# Injizierbare Fehler (werden reihum kombiniert, s. SZENARIEN):
#     german_note      rein deutsche Fertigungsanmerkung einfügen
#     weld_note        Schweißangabe einfügen (erzeugt ggf. Werkstoff-Widerspruch)
#     set_material     Werkstoffangabe auf 1.4305 umschreiben (Widerspruchstest)
#     remove_gentol    Allgemeintoleranz-Angabe (ISO 2768/22081) wegretuschieren
#     remove_edges     Kantenzustand (ISO 13715) wegretuschieren
#     obsolete_norm    veralteten Normbezug (DIN 7168) einfügen
#     rasterize        Zeichnung in Scan ohne Textlayer verwandeln
#     vague_note       unbestimmte Angaben ("ca.", "nach Absprache", TBD)
#     house_norm       Verweis auf eine nicht beziehbare Werknorm
#     impossible_mass  unmögliche Gewichtsangabe (Faktor 1000, g/kg vertauscht)
#     plating_note     galvanische Beschichtung an hochfestem Teil ohne
#                      Entsprödung (EN ISO 4042)
import sys
import zipfile
from pathlib import Path

import pymupdf

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


# ------------------------------------------------------------- Manipulationen
def _insert_note(page: pymupdf.Page, lines: list[str], anchor: str) -> str:
    """Fügt einen Textblock in einer freien Ecke oberhalb des Schriftfelds ein."""
    rect = page.rect
    x = rect.width * 0.55
    y = rect.height * 0.60
    kwargs = {}
    if Path(FONT).exists():
        page.insert_font(fontname="INJ", fontfile=FONT)
        kwargs["fontname"] = "INJ"
    for i, line in enumerate(lines):
        page.insert_text((x, y + i * 13), line, fontsize=9, **kwargs)
    return f"{anchor}: Textblock bei ({x:.0f},{y:.0f}) eingefügt"


def german_note(doc: pymupdf.Document) -> str:
    return _insert_note(doc[0], [
        "Zusätzliche Anmerkungen:",
        "1. Alle Kanten gratfrei, scharfkantige Übergänge gebrochen.",
        "2. Teile vor Auslieferung konservieren und einzeln verpacken.",
        "3. Rückfragen ausschließlich an die Fertigungsplanung.",
    ], "german_note")


def weld_note(doc: pymupdf.Document) -> str:
    return _insert_note(doc[0], [
        "Schweißnaht a4 umlaufend, ISO 5817-C",
    ], "weld_note")


def vague_note(doc: pymupdf.Document) -> str:
    return _insert_note(doc[0], [
        "Fertigungshinweise:",
        "Bohrung ca. 12 mm, Lage nach Absprache.",
        "Kanten sauber entgraten, Oberfläche wie Muster.",
        "Beschichtung: TBD",
    ], "vague_note")


def house_norm(doc: pymupdf.Document) -> str:
    return _insert_note(doc[0], [
        "Oberflächenschutz nach WN 51204",
        "Prüfumfang nach TL 245",
    ], "house_norm")


def impossible_mass(doc: pymupdf.Document) -> str:
    return _insert_note(doc[0], [
        "Werkstoff: S235JR",
        "Gewicht: 4200 kg",
    ], "impossible_mass")


def plating_note(doc: pymupdf.Document) -> str:
    return _insert_note(doc[0], [
        "Werkstoff: 42CrMo4, vergütet 45 HRC",
        "galvanisch verzinkt nach ISO 2081, 8 µm",
    ], "plating_note")


def obsolete_norm(doc: pymupdf.Document) -> str:
    return _insert_note(doc[0], [
        "Allgemeintoleranzen DIN 7168-m",
    ], "obsolete_norm")


def set_material(doc: pymupdf.Document, new: str = "1.4305") -> str:
    """Ersetzt die erste erkannte Werkstoffbezeichnung durch `new`."""
    from drawing_checker.pruef_werkstoff import MATERIALS
    import re

    for page in doc:
        text = page.get_text()
        for mat in MATERIALS:
            for pat in mat.patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if not m:
                    continue
                quads = page.search_for(m.group(0))
                if not quads:
                    continue
                r = quads[0]
                page.add_redact_annot(r, fill=(1, 1, 1))
                page.apply_redactions()
                kwargs = {}
                if Path(FONT).exists():
                    page.insert_font(fontname="INJ2", fontfile=FONT)
                    kwargs["fontname"] = "INJ2"
                page.insert_text((r.x0, r.y1 - 1), new,
                                 fontsize=max(7, r.height * 0.8), **kwargs)
                return (f"set_material: „{m.group(0)}“ → „{new}“ "
                        f"auf Seite {page.number + 1}")
    return "set_material: keine erkennbare Werkstoffangabe gefunden (übersprungen)"


def _remove_pattern(doc: pymupdf.Document, needles: list[str], name: str) -> str:
    for page in doc:
        for needle in needles:
            for r in page.search_for(needle):
                page.add_redact_annot(r, fill=(1, 1, 1))
                page.apply_redactions()
                return f"{name}: „{needle}“ auf Seite {page.number + 1} entfernt"
    return f"{name}: Muster nicht gefunden (übersprungen)"


def remove_gentol(doc: pymupdf.Document) -> str:
    return _remove_pattern(doc, ["ISO 2768", "ISO 22081"], "remove_gentol")


def remove_edges(doc: pymupdf.Document) -> str:
    return _remove_pattern(doc, ["ISO 13715"], "remove_edges")


MANIPULATIONS = {
    "german_note": german_note,
    "weld_note": weld_note,
    "set_material": set_material,
    "remove_gentol": remove_gentol,
    "remove_edges": remove_edges,
    "obsolete_norm": obsolete_norm,
    "vague_note": vague_note,
    "house_norm": house_norm,
    "impossible_mass": impossible_mass,
    "plating_note": plating_note,
}

# Reihum angewandte Fehlerkombinationen für aufeinanderfolgende Zeichnungen.
SZENARIEN: list[list[str]] = [
    ["german_note", "remove_gentol"],
    ["set_material", "weld_note"],
    ["obsolete_norm", "remove_edges"],
    ["german_note", "set_material"],
    ["vague_note", "house_norm"],
    ["impossible_mass", "remove_edges"],
    ["plating_note", "german_note"],
]


# --------------------------------------------------------------------- Aufbau
def _quellordner(source: Path) -> Path:
    """Ordner mit den Zeichnungen – auch wenn nur das Archiv da ist.

    Die Kalibrierzeichnungen liegen als ein ZIP im Repository. Zeigt
    `source` auf den (nicht ausgepackten) Ordner oder auf das Archiv
    selbst, wird hier ausgepackt.
    """
    if source.is_dir() and any(source.glob("*.pdf")):
        return source
    from .quellen import zeichnungen

    return zeichnungen()


def build(source: Path, target: Path, start_matnr: int = 20500001) -> None:
    import openpyxl
    from openpyxl.styles import Font

    source = _quellordner(source)
    pdfs = sorted(source.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"Keine PDFs in {source} gefunden")
    target.mkdir(parents=True, exist_ok=True)
    manifest: list[str] = []
    rows: list[tuple[str, str]] = []
    matnr = start_matnr

    for i, pdf in enumerate(pdfs):
        step = next((p for ext in (".stp", ".step")
                     for p in [pdf.with_suffix(ext)] if p.exists()), None)

        # 1) Referenzpaket: unverändert
        _pack(target, str(matnr), pdf.read_bytes(), pdf.name, step)
        rows.append((str(matnr), f"{pdf.stem} (Original)"))
        manifest.append(f"{matnr}: {pdf.name} unverändert (Referenz)")
        matnr += 1

        # 2) Fehlerpaket: Szenario reihum
        szenario = SZENARIEN[i % len(SZENARIEN)]
        doc = pymupdf.open(pdf)
        applied = [MANIPULATIONS[s](doc) for s in szenario]
        data = doc.tobytes(deflate=True)
        doc.close()
        _pack(target, str(matnr), data, pdf.name, step)
        rows.append((str(matnr), f"{pdf.stem} (Fehler injiziert)"))
        manifest.append(f"{matnr}: {pdf.name} + " + "; ".join(applied))
        matnr += 1

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Materialliste"
    ws.append(["Lfd.Nr.", "Werk", "Materialnummer", "Benennung"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for i, (nr, name) in enumerate(rows, start=1):
        ws.append([i, "1000", nr, name])
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 40
    wb.save(target / "Materialliste_Echt.xlsx")
    (target / "MANIFEST.txt").write_text("\n".join(manifest), encoding="utf-8")
    print(f"{len(rows)} Pakete erzeugt in {target} (siehe MANIFEST.txt)")


def _pack(target: Path, matnr: str, pdf_bytes: bytes, pdf_name: str,
          step: Path | None) -> None:
    with zipfile.ZipFile(target / f"{matnr}.zip", "w",
                         zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(pdf_name, pdf_bytes)
        if step is not None:
            zf.write(step, step.name)


# ======================================================================
# Einstieg
# ======================================================================
def main(argv: list[str] | None = None) -> int:
    """Verteilt auf die Unterbefehle."""
    argv = list(sys.argv[1:] if argv is None else argv)
    befehl = argv[0] if argv else ""
    rest = argv[1:]

    if befehl == "bauen":
        ziel = Path(rest[0]) if rest else Path(__file__).parent / "out"
        build_all(ziel)
        print(f"Mockpakete gebaut nach: {ziel}")
        return 0
    if befehl == "quellen":
        ordner = zeichnungen()
        pdf, step = anzahl()
        print(f"{pdf} Zeichnungen, {step} STEP-Modelle ausgepackt nach:")
        print(f"  {ordner}")
        return 0
    if befehl == "fehler":
        if len(rest) != 2:
            print("Aufruf: python -m mockdata fehler <quellordner> <zielordner>")
            return 2
        build(Path(rest[0]), Path(rest[1]))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
