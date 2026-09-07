"""Messplatz für den OCR-Fallback.

Nimmt echte Zeichnungen MIT Textlayer, rastert sie (erzeugt also einen
„Scan" mit bekannter Wahrheit) und misst, wie viel der OCR-Pfad davon
zurückgewinnt. Damit ist die OCR-Qualität eine Zahl statt eines Gefühls.

    python -m tools.ocr_bench [ordner] [--dpi 200] [--noise]

Gemessen wird:
  Token-Recall      Anteil der Wahrheits-Token, die die OCR wiederfindet
  Maß-Recall        dasselbe nur für maßrelevante Token (Zahlen, ⌀, M12 …)
  Maße              extrahierte Maßwerte OCR vs. Wahrheit (Schnittmenge)
  Findings          Regelbefunde OCR vs. Wahrheit (Abweichung = Fehlurteil)

Der Scan wird bewusst realistisch verschlechtert (Auflösung, Rauschen,
leichte Schräglage), damit die Messung nicht zu optimistisch ausfällt.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
import tempfile
from pathlib import Path

import pymupdf

# Token, die für die Prüfung zählen (Maße, Werkstoffe, Normen).
RE_RELEVANT = re.compile(r"[⌀ØR]?\d|M\d|ISO|DIN|EN\b|Ra|Rz|H\d|h\d", re.IGNORECASE)


def rasterize(pdf: Path, out: Path, dpi: int = 200, noise: bool = True,
              skew_deg: float = 0.0) -> Path:
    """Erzeugt aus einem Vektor-PDF ein Scan-PDF ohne Textlayer."""
    import numpy as np
    from PIL import Image

    src = pymupdf.open(pdf)
    dst = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
        img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        if skew_deg:
            img = img.rotate(skew_deg, resample=Image.BICUBIC, fillcolor=255,
                             expand=True)
        if noise:
            arr = np.asarray(img).astype(np.int16)
            rng = np.random.default_rng(42)
            arr = arr + rng.normal(0, 12, arr.shape)
            img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        new = dst.new_page(width=page.rect.width, height=page.rect.height)
        buf = _png_bytes(img)
        new.insert_image(new.rect, stream=buf)
    dst.save(out)
    dst.close()
    src.close()
    return out


def _png_bytes(img) -> bytes:
    import io

    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()


def _tokens(words: list[str]) -> tuple[set[str], set[str]]:
    alle = {w for w in words if len(w) > 1}
    return alle, {w for w in alle if RE_RELEVANT.search(w)}


def analyse(pdf_path: Path) -> dict:
    """Ein Durchgang: Token, Maße und Findings eines PDFs (wie im Lauf)."""
    from drawing_checker.regeln import CheckContext, load_profile
    from drawing_checker.pruef_zeichnung import run_drawing_checks
    from drawing_checker.kern import PackageContent
    from drawing_checker.zeichnung import extract_dimensions
    from drawing_checker.zeichnung import DrawingPdf

    with DrawingPdf(pdf_path) as pdf:
        ctx = CheckContext("bench", pdf, PackageContent(),
                           load_profile("default"))
        run_drawing_checks(ctx)
        dims = {round(d.value, 1) for d in extract_dimensions(pdf, 6000)}
        alle, relevant = _tokens([w.text.strip() for w in pdf.words()
                                  if w.text.strip()])
        return {"dims": dims, "codes": {f.code for f in ctx.findings},
                "ocr": pdf.ocr_used, "tokens": alle, "relevant": relevant}


def run(source: Path, dpi: int, noise: bool, skew: float) -> int:
    if not (source.is_dir() and any(source.glob("*.pdf"))):
        # Kalibrierzeichnungen liegen als ein Archiv im Repository.
        from mockdata.quellen import zeichnungen

        source = zeichnungen()
    pdfs = sorted(source.glob("*.pdf"))
    if not pdfs:
        print(f"Keine PDFs in {source}")
        return 2
    tmp = Path(tempfile.mkdtemp(prefix="ocrbench_"))
    rows = []
    for pdf in pdfs:
        truth = analyse(pdf)
        if len(truth["tokens"]) < 20:
            continue                      # selbst schon ein Scan
        scan = rasterize(pdf, tmp / f"{pdf.stem}_scan.pdf", dpi=dpi,
                         noise=noise, skew_deg=skew)
        got = analyse(scan)
        rows.append({
            "name": pdf.stem,
            "recall": _recall(truth["tokens"], got["tokens"]),
            "recall_rel": _recall(truth["relevant"], got["relevant"]),
            "dims_truth": len(truth["dims"]),
            "dims_hit": len(truth["dims"] & got["dims"]),
            "dims_extra": len(got["dims"] - truth["dims"]),
            "codes_miss": len(truth["codes"] - got["codes"]),
            "codes_extra": len(got["codes"] - truth["codes"]),
            "ocr": got["ocr"],
        })
    _print(rows, dpi, noise, skew)
    return 0


def _recall(truth: set[str], got: set[str]) -> float:
    """Anteil der Wahrheits-Token, die (unscharf) wiedergefunden wurden."""
    if not truth:
        return 1.0
    got_norm = {_norm(g) for g in got}
    hit = sum(1 for t in truth if _norm(t) in got_norm)
    return hit / len(truth)


def _norm(s: str) -> str:
    return re.sub(r"[\s,.;:]", "", s).upper()


def _print(rows: list[dict], dpi: int, noise: bool, skew: float) -> None:
    print(f"OCR-Messlauf  (Scan {dpi} dpi, Rauschen={'ja' if noise else 'nein'}, "
          f"Schraeglage={skew} Grad)")
    header = (f"{'Zeichnung':<22}{'Token':>7}{'Masstok':>9}{'Masse':>10}"
              f"{'Fehlmasse':>11}{'Regeln -/+':>12}")
    print(header)
    for r in rows:
        dims = f"{r['dims_hit']}/{r['dims_truth']}"
        regeln = "-%d/+%d" % (r["codes_miss"], r["codes_extra"])
        print(f"{r['name']:<22}{r['recall']:>6.0%}{r['recall_rel']:>9.0%}"
              f"{dims:>10}{r['dims_extra']:>11}{regeln:>12}")
    if not rows:
        return
    n = len(rows)
    dims = "%d/%d" % (sum(r["dims_hit"] for r in rows),
                      sum(r["dims_truth"] for r in rows))
    regeln = "-%d/+%d" % (sum(r["codes_miss"] for r in rows),
                          sum(r["codes_extra"] for r in rows))
    print("-" * len(header))
    print(f"{'Mittel':<22}{sum(r['recall'] for r in rows) / n:>6.0%}"
          f"{sum(r['recall_rel'] for r in rows) / n:>9.0%}"
          f"{dims:>10}{sum(r['dims_extra'] for r in rows):>11}{regeln:>12}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path, nargs="?",
                    default=Path("mockdata/echt_quellen"),
                    help="Ordner mit Zeichnungen; ohne Angabe die echten "
                         "Kalibrierzeichnungen aus dem Archiv")
    ap.add_argument("--dpi", type=int, default=200,
                    help="Auflösung des simulierten Scans")
    ap.add_argument("--no-noise", action="store_true")
    ap.add_argument("--skew", type=float, default=0.0,
                    help="Schräglage des Scans in Grad")
    a = ap.parse_args(argv)
    return run(a.source, a.dpi, not a.no_noise, a.skew)


if __name__ == "__main__":
    sys.exit(main())
