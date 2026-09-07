"""Messplaetze und Auswertungen - ein Werkzeugkasten mit Unterbefehlen.

    python -m tools.messen ocr [ordner] [--dpi 200]   OCR-Guete messen
    python -m tools.messen langlauf --count 200       Speicher/Platte/Zeit
    python -m tools.messen kalibrier <ordner>         Fehlalarme vs. Treffer
    python -m tools.messen normen <csv> <yaml>        Normstatus importieren

Vier Werkzeuge, die alle dasselbe tun: eine Behauptung ueber das Tool in
eine Zahl verwandeln. Sie lagen als vier Dateien nebeneinander - als ein
Werkzeugkasten mit Unterbefehlen sind sie leichter zu finden.
"""
from __future__ import annotations

# ======================================================================
# ocr_bench
# ======================================================================
# Messplatz für den OCR-Fallback.
#
# Nimmt echte Zeichnungen MIT Textlayer, rastert sie (erzeugt also einen
# „Scan" mit bekannter Wahrheit) und misst, wie viel der OCR-Pfad davon
# zurückgewinnt. Damit ist die OCR-Qualität eine Zahl statt eines Gefühls.
#
#     python -m tools.ocr_bench [ordner] [--dpi 200] [--noise]
#
# Gemessen wird:
#   Token-Recall      Anteil der Wahrheits-Token, die die OCR wiederfindet
#   Maß-Recall        dasselbe nur für maßrelevante Token (Zahlen, ⌀, M12 …)
#   Maße              extrahierte Maßwerte OCR vs. Wahrheit (Schnittmenge)
#   Findings          Regelbefunde OCR vs. Wahrheit (Abweichung = Fehlurteil)
#
# Der Scan wird bewusst realistisch verschlechtert (Auflösung, Rauschen,
# leichte Schräglage), damit die Messung nicht zu optimistisch ausfällt.
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


def run_ocr(source: Path, dpi: int, noise: bool, skew: float) -> int:
    if not (source.is_dir() and any(source.glob("*.pdf"))):
        # Kalibrierzeichnungen liegen als ein Archiv im Repository.
        from mockdata.daten import zeichnungen

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


def main_ocr(argv: list[str] | None = None) -> int:
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
    return run_ocr(a.source, a.dpi, not a.no_noise, a.skew)


# ======================================================================
# langlauf
# ======================================================================
# Langlauf-Test: verhält sich das Tool über hunderte Materialnummern sauber?
#
# Der Echtlauf geht über eine ganze Materialgruppe – mehrere hundert Zeilen,
# Stunden Laufzeit, unbeaufsichtigt. Dieser Test beantwortet vorher die
# Fragen, die dabei den Lauf kosten können:
#
#   * Wächst der Speicherbedarf mit der Zeit (Leck in PDF/OCR/STEP)?
#   * Wächst der Ergebnisordner unbegrenzt, oder greift das Aufräumen?
#   * Bleibt die Zeit je Materialnummer konstant?
#
#     python -m tools.langlauf --count 200 [--quelle mockdata/out] [--keep]
#
# Die Pakete werden aus vorhandenen Mockpaketen vervielfältigt; geprüft wird
# mit dem normalen Orchestrator über den Mock-Adapter, also demselben Weg wie
# im Echtbetrieb (nur ohne SAP).
import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path


def rss_mb() -> float:
    """Aktueller Speicherbedarf des Prozesses in MB (0 = nicht messbar)."""
    try:                                     # Linux
        with open("/proc/self/statm", encoding="ascii") as fh:
            pages = int(fh.read().split()[1])
        return pages * 4096 / (1024 * 1024)
    except OSError:
        pass
    try:                                     # Unix allgemein: nur Spitzenwert
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak / 1024
    except Exception:
        return 0.0


def build_liste(quelle: Path, ziel: Path, count: int) -> Path:
    """Erzeugt `count` Pakete (Kopien der Vorlagen) plus Input-Excel."""
    import openpyxl

    vorlagen = sorted(quelle.glob("*.zip"))
    if not vorlagen:
        raise SystemExit(f"Keine ZIP-Pakete in {quelle} – erst "
                         f"`python -m mockdata bauen` laufen lassen.")
    ziel.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Materialliste"
    ws.append(["Lfd.Nr.", "Werk", "Materialnummer", "Benennung"])
    for i in range(count):
        matnr = f"9{i + 1:07d}"
        shutil.copy2(vorlagen[i % len(vorlagen)], ziel / f"{matnr}.zip")
        ws.append([i + 1, "1000", matnr, f"Langlauf {i + 1}"])
    excel = ziel / "Langlauf.xlsx"
    wb.save(excel)
    return excel


def run_langlauf(count: int, quelle: Path, keep: bool) -> int:
    from drawing_checker.kern import dir_size_mb, free_mb
    from drawing_checker.kern import RunConfig
    from drawing_checker.ablauf import Callbacks, Orchestrator
    from drawing_checker.sap_ymatdocs import MockSapAdapter

    tmp = Path(tempfile.mkdtemp(prefix="langlauf_"))
    pakete = tmp / "pakete"
    excel = build_liste(quelle, pakete, count)
    out = tmp / "Ergebnisse"

    config = RunConfig(excel_path=excel, sheet_name="Materialliste",
                       material_column="C", header_row=1, output_dir=out,
                       keep_packages=keep)
    adapter = MockSapAdapter(pakete)
    adapter.ensure_ready()

    proben: list[tuple[int, float, float, float]] = []
    start_rss = rss_mb()
    t0 = time.time()

    def on_result(_r):
        n = orch.progress.done + 1
        if n % max(count // 10, 1) == 0 or n == 1:
            proben.append((n, time.time() - t0, rss_mb(),
                           dir_size_mb(orch.run_dir)))

    orch = Orchestrator(config, adapter, Callbacks(on_result=on_result))
    orch.start()
    orch.join(timeout=3600)
    dauer = time.time() - t0

    print(f"\nLanglauf über {count} Materialnummern")
    print(f"{'nach':>6}{'Sekunden':>10}{'Speicher MB':>13}{'Ordner MB':>11}")
    for n, sek, rss, mb in proben:
        print(f"{n:>6}{sek:>10.0f}{rss:>13.0f}{mb:>11.1f}")
    ende_rss = rss_mb()
    print(f"\nGesamtdauer      {dauer:.0f} s "
          f"({dauer / max(count, 1):.2f} s je Materialnummer)")
    print(f"Speicher         {start_rss:.0f} -> {ende_rss:.0f} MB "
          f"(Zuwachs {ende_rss - start_rss:+.0f} MB)")
    print(f"Ergebnisordner   {dir_size_mb(orch.run_dir):.1f} MB")
    print(f"Frei auf Platte  {free_mb(out):.0f} MB")
    print(f"Ergebnis         {orch.progress.message}")

    # Bewertung
    fehler = []
    # Bewertet wird der Zuwachs NACH dem Warmlaufen (Bibliotheken laden
    # einmalig einige hundert MB); entscheidend ist, ob es danach weiter
    # wächst.
    if len(proben) >= 3:
        warm = proben[1][2]
        zuwachs = proben[-1][2] - warm
        je_stueck = zuwachs / max(proben[-1][0] - proben[1][0], 1)
        print(f"Nach dem Warmlaufen {warm:.0f} MB, am Ende "
              f"{proben[-1][2]:.0f} MB ({zuwachs:+.0f} MB, "
              f"{je_stueck:+.2f} MB je Materialnummer)")
        if je_stueck > 1.0:
            fehler.append(f"Speicher wächst um {je_stueck:.1f} MB je "
                          f"Materialnummer – Verdacht auf ein Leck")
    if not keep and dir_size_mb(orch.run_dir / "pakete") > 50:
        fehler.append("Paketordner wurde nicht aufgeräumt")
    if orch.progress.failed:
        fehler.append(f"{orch.progress.failed} Materialnummern fehlgeschlagen")
    if len(proben) >= 4:
        erst = proben[1][1] - proben[0][1]
        letzt = proben[-1][1] - proben[-2][1]
        if erst > 0 and letzt > erst * 3:
            fehler.append("Prüfung wird im Verlauf deutlich langsamer")
    shutil.rmtree(tmp, ignore_errors=True)
    if fehler:
        print("\nBEFUND:")
        for f in fehler:
            print(f"  - {f}")
        return 1
    print("\nBefund: unauffällig (Speicher stabil, Ordner aufgeräumt, "
          "keine Ausfälle).")
    return 0


def main_langlauf(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", type=int, default=200)
    ap.add_argument("--quelle", type=Path, default=Path("mockdata/out"))
    ap.add_argument("--keep", action="store_true",
                    help="Pakete behalten (prüft den Gegenfall)")
    a = ap.parse_args(argv)
    return run_langlauf(a.count, a.quelle, a.keep)


# ======================================================================
# kalibrier_auswertung
# ======================================================================
# Wertet einen Kalibrierlauf aus: Fehlalarme vs. gefundene Injektionen.
#
#     python -m mockdata fehler mockdata/echt_quellen /tmp/kal
#     python -m drawing_checker.app --headless --mock /tmp/kal         --excel /tmp/kal/Materialliste_Echt.xlsx --column C
#     python -m tools.kalibrier_auswertung /tmp/kal
#
# Die Referenzpakete (unveränderte Originalzeichnungen) sind der Maßstab für
# Fehlalarme: Was dort als Fehler gemeldet wird, ist mit hoher
# Wahrscheinlichkeit einer. Die Fehlerpakete zeigen, ob die Injektionen
# gefunden werden.
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path


def lade_manifest(ordner: Path) -> dict[str, str]:
    """{Materialnummer: 'Referenz' | Injektionsbeschreibung}"""
    art: dict[str, str] = {}
    for zeile in (ordner / "MANIFEST.txt").read_text(encoding="utf-8").splitlines():
        if ":" not in zeile:
            continue
        matnr, rest = zeile.split(":", 1)
        art[matnr.strip()] = ("Referenz" if "unverändert" in rest
                              else rest.strip())
    return art


def lade_findings(lauf: Path) -> list[dict]:
    with open(lauf / "findings.csv", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def auswerten(ordner: Path) -> int:
    laeufe = sorted((ordner / "Ergebnisse").glob("lauf_*"), reverse=True)
    if not laeufe:
        print(f"Kein Lauf in {ordner / 'Ergebnisse'} gefunden.")
        return 2
    art = lade_manifest(ordner)
    rows = lade_findings(laeufe[0])

    ref_codes: Counter = Counter()
    err_codes: Counter = Counter()
    ref_hart: Counter = Counter()
    referenzen = {m for m, a in art.items() if a == "Referenz"}
    fehlerhafte = set(art) - referenzen
    for r in rows:
        matnr, code, bewertung = r["Materialnummer"], r["Regel"], r["Bewertung"]
        if matnr in referenzen:
            ref_codes[code] += 1
            if bewertung in ("Fehler", "K.O."):
                ref_hart[code] += 1
        else:
            err_codes[code] += 1

    print(f"Kalibrierlauf: {laeufe[0].name}")
    print(f"{len(referenzen)} Referenzzeichnungen, {len(fehlerhafte)} mit "
          f"injizierten Fehlern\n")
    print("Meldungen auf den UNVERÄNDERTEN Referenzzeichnungen")
    print("(Fehler/K.O. hier sind Fehlalarm-Verdacht):")
    print(f"{'Regel':<26}{'gesamt':>8}{'davon hart':>12}{'je Zeichnung':>14}")
    for code, n in ref_codes.most_common():
        print(f"{code:<26}{n:>8}{ref_hart.get(code, 0):>12}"
              f"{n / max(len(referenzen), 1):>14.2f}")
    print(f"\nHarte Meldungen auf Referenzen gesamt: {sum(ref_hart.values())}"
          f" (in {len(ref_hart)} Regeln)")
    nur_fehler = set(err_codes) - set(ref_codes)
    print(f"\nNur auf den Fehlerpaketen ausgelöst ({len(nur_fehler)} Regeln): "
          + (", ".join(sorted(nur_fehler)) or "keine"))
    return 0


def main_kalibrier(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ordner", type=Path)
    return auswerten(ap.parse_args(argv).ordner)


# ======================================================================
# import_norms_csv
# ======================================================================
# Massenimport von Normstatus-Daten in das Normen-Wissenspaket.
#
# Konvertiert einen Export der Normenverwaltung (Nautos/Perinorm o. ä.) in
# norms-Einträge. Erwartetes CSV (Trennzeichen ; oder ,):
#
#     Dokumentnummer;Status;Nachfolger
#     DIN 7168;zurückgezogen;ISO 2768
#     ISO 1302;ersetzt;ISO 21920-1
#     ISO 13715;gültig;
#
# Nur Zeilen mit Status != gültig werden übernommen. Ausgabe ist eine
# YAML-Datei, die als zusätzliches Paket neben norms.yaml gelegt wird
# (drawing_checker/rules/norms_firma.yaml) und automatisch mitlädt.
#
# Aufruf:
#     python -m tools.messen normen export.csv drawing_checker/rules/norms_firma.yaml
import csv
import re
import sys
from pathlib import Path

VALID = {"gültig", "gueltig", "aktuell", "valid", "current"}


def norm_to_pattern(norm: str) -> str:
    """„DIN EN ISO 1302“ -> robustes Regex mit optionalen Präfixen."""
    m = re.match(r"^\s*((?:DIN|EN|ISO|VDI|VDE|ASME|ANSI|AWS|\s)+)?\s*"
                 r"([\dXY.\-/]+[\w.\-/]*)\s*$", norm, re.IGNORECASE)
    if not m:
        raise ValueError(f"Normbezeichnung nicht interpretierbar: {norm!r}")
    prefixes = (m.group(1) or "").split()
    number = re.escape(m.group(2))
    if not prefixes:
        raise ValueError(f"Norm ohne Präfix (DIN/ISO/…): {norm!r}")
    # Letztes Präfix ist Pflicht, alles davor optional (DIN EN ISO == ISO).
    haupt = prefixes[-1]
    return rf"(?:DIN\s*)?(?:EN\s*)?{haupt}\s*{number}\b"


def convert(csv_path: Path, out_path: Path) -> int:
    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        delim = ";" if sample.count(";") >= sample.count(",") else ","
        for row in csv.reader(fh, delimiter=delim):
            if len(row) < 2 or row[0].strip().lower() in ("dokumentnummer",
                                                          "norm", "nummer"):
                continue
            norm, status = row[0].strip(), row[1].strip().lower()
            successor = row[2].strip() if len(row) > 2 else ""
            if not norm or status in VALID:
                continue
            msg = f"{norm} ist {row[1].strip()}"
            if successor:
                msg += f" – Nachfolger: {successor}"
            try:
                rows.append((norm_to_pattern(norm), msg))
            except ValueError as exc:
                print(f"übersprungen: {exc}", file=sys.stderr)

    lines = ["# Automatisch importiert aus " + csv_path.name,
             "# (python -m tools.messen normen) – manuell nachschärfen erlaubt.",
             "", "obsolete:"]
    for pattern, msg in rows:
        p = pattern.replace("'", "''")
        m = msg.replace("'", "''")
        lines.append(f"  - {{pattern: '{p}',")
        lines.append(f"     message: '{m}'}}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} Einträge -> {out_path}")
    return len(rows)


def main_normen(argv: list[str] | None = None) -> int:
    """Normstatus-CSV in ein YAML-Wissenspaket wandeln."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print("Aufruf: python -m tools.messen normen <export.csv> <ziel.yaml>")
        return 2
    convert(Path(argv[0]), Path(argv[1]))
    return 0


# ======================================================================
# Einstieg
# ======================================================================
def main(argv: list[str] | None = None) -> int:
    """Verteilt auf die Unterbefehle."""
    import sys as _sys

    argv = list(_sys.argv[1:] if argv is None else argv)
    befehle = {"ocr": main_ocr, "langlauf": main_langlauf,
               "kalibrier": main_kalibrier, "normen": main_normen}
    if not argv or argv[0] not in befehle:
        print(__doc__)
        return 2
    return befehle[argv[0]](argv[1:])


if __name__ == "__main__":
    import sys

    sys.exit(main())
