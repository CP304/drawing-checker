import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def mock_dir(tmp_path_factory) -> Path:
    """Erzeugt die Mockdaten einmal je Testlauf (Zeichnungen, STEP, ZIPs, Excel)."""
    out = tmp_path_factory.mktemp("mockdaten")
    from mockdata.daten import build_all

    build_all(out)
    return out


# --------------------------------------------------------- gemeinsame Hilfen
# Diese Helfer standen vorher in bis zu sechs Testdateien fast wortgleich
# nebeneinander. Beim Zusammenlegen der Tests wurden daraus eine Fassung.
# Import in den Testdateien:  from conftest import make_ctx, codes, ...

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FIXTURE = Path(__file__).parent / "fixtures" / "ymatdocs_beispiel.vbs"


def echte_zeichnungen() -> Path:
    """Ordner mit den Kalibrierzeichnungen (liegen als ein Archiv im Repo)."""
    from mockdata.daten import zeichnungen

    try:
        return zeichnungen()
    except FileNotFoundError:
        return Path("/nicht/vorhanden")


ECHT = echte_zeichnungen()


def make_ctx(tmp_path, items, profile: str = "default",
             pages: int = 1, name: str = "t.pdf"):
    """Baut ein Prüf-PDF aus Textzeilen und liefert den Prüfkontext.

    `items` ist je Eintrag entweder nur Text (untereinander in der linken
    Spalte), `(x, text)` für eine eigene Spalte oder `(x, y, text)` für eine
    exakte Position – letzteres brauchen die GPS-Prüfungen, bei denen der
    Abstand zwischen zwei Angaben die Aussage trägt.

    Angehängt wird immer eine Füllzeile: unter 40 Zeichen gilt eine Seite
    als „ohne Textlayer", und dann liefe die OCR statt der Textauswertung.
    """
    import pymupdf

    from drawing_checker.kern import PackageContent
    from drawing_checker.regeln import CheckContext, load_profile
    from drawing_checker.zeichnung import DrawingPdf

    doc = pymupdf.open()
    for pno in range(pages):
        page = doc.new_page(width=842, height=595)
        kwargs = {}
        if Path(FONT).exists():
            page.insert_font(fontname="T", fontfile=FONT)
            kwargs["fontname"] = "T"
        if pno:
            continue
        y = 60
        eintraege = list(items) + [
            "Interne Testzeichnung - Blatt 1 von 1, Ausgabestand 2026"]
        for eintrag in eintraege:
            if isinstance(eintrag, tuple) and len(eintrag) == 3:
                x, yy, text = eintrag
            elif isinstance(eintrag, tuple):
                (x, text), yy = eintrag, y
                y += 30
            else:
                x, yy, text = 40, y, eintrag
                y += 30
            page.insert_text((x, yy), text, fontsize=10, **kwargs)
    pfad = tmp_path / name
    doc.save(pfad)
    doc.close()
    return CheckContext("123", DrawingPdf(pfad), PackageContent(),
                        load_profile(profile))


def codes(ctx, *pruefungen) -> dict:
    """Prüfungen laufen lassen und die Befunde nach Regelcode aufschlüsseln."""
    for pruefung in pruefungen:
        pruefung(ctx)
    return {f.code: f for f in ctx.findings}


def make_config(mock_dir: Path, out: Path, **kw):
    """Standard-Laufkonfiguration gegen die Mockdaten."""
    from drawing_checker.kern import RunConfig

    basis = dict(
        excel_path=mock_dir / "Materialliste_Mock.xlsx",
        sheet_name="Materialliste", material_column="C", header_row=1,
        output_dir=out, material_group="default",
    )
    basis.update(kw)
    return RunConfig(**basis)
