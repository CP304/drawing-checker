"""Baut aus ECHTEN Zeichnungen alter Prüfungen Mock-Pakete mit eingebauten Fehlern.

Gedacht für die Kalibrierung des Checkers an realen Daten: einen Ordner mit
echten PDFs (und optional passenden STEP-Dateien) hineingeben, das Skript
erzeugt je Zeichnung YMATDOCS-artige ZIPs – einmal unverändert (Referenz)
und einmal mit gezielt injizierten Fehlern – plus Input-Excel und ein
Manifest, das dokumentiert, welcher Fehler wo eingebaut wurde.

Aufruf:
    python -m mockdata.inject_errors QUELLORDNER ZIELORDNER

Konventionen im Quellordner:
    <name>.pdf            die Zeichnung (Pflicht)
    <name>.stp/.step      zugehöriges STEP (optional)

Injizierbare Fehler (werden reihum kombiniert, s. SZENARIEN):
    german_note      rein deutsche Fertigungsanmerkung einfügen
    weld_note        Schweißangabe einfügen (erzeugt ggf. Werkstoff-Widerspruch)
    set_material     Werkstoffangabe auf 1.4305 umschreiben (Widerspruchstest)
    remove_gentol    Allgemeintoleranz-Angabe (ISO 2768/22081) wegretuschieren
    remove_edges     Kantenzustand (ISO 13715) wegretuschieren
    obsolete_norm    veralteten Normbezug (DIN 7168) einfügen
    rasterize        Zeichnung in Scan ohne Textlayer verwandeln
"""
from __future__ import annotations

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


def obsolete_norm(doc: pymupdf.Document) -> str:
    return _insert_note(doc[0], [
        "Allgemeintoleranzen DIN 7168-m",
    ], "obsolete_norm")


def set_material(doc: pymupdf.Document, new: str = "1.4305") -> str:
    """Ersetzt die erste erkannte Werkstoffbezeichnung durch `new`."""
    from drawing_checker.checks.materials import MATERIALS
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
}

# Reihum angewandte Fehlerkombinationen für aufeinanderfolgende Zeichnungen.
SZENARIEN: list[list[str]] = [
    ["german_note", "remove_gentol"],
    ["set_material", "weld_note"],
    ["obsolete_norm", "remove_edges"],
    ["german_note", "set_material"],
]


# --------------------------------------------------------------------- Aufbau
def build(source: Path, target: Path, start_matnr: int = 20500001) -> None:
    import openpyxl
    from openpyxl.styles import Font

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


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    build(Path(sys.argv[1]), Path(sys.argv[2]))
