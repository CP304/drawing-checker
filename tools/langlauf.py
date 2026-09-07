"""Langlauf-Test: verhält sich das Tool über hunderte Materialnummern sauber?

Der Echtlauf geht über eine ganze Materialgruppe – mehrere hundert Zeilen,
Stunden Laufzeit, unbeaufsichtigt. Dieser Test beantwortet vorher die
Fragen, die dabei den Lauf kosten können:

  * Wächst der Speicherbedarf mit der Zeit (Leck in PDF/OCR/STEP)?
  * Wächst der Ergebnisordner unbegrenzt, oder greift das Aufräumen?
  * Bleibt die Zeit je Materialnummer konstant?

    python -m tools.langlauf --count 200 [--quelle mockdata/out] [--keep]

Die Pakete werden aus vorhandenen Mockpaketen vervielfältigt; geprüft wird
mit dem normalen Orchestrator über den Mock-Adapter, also demselben Weg wie
im Echtbetrieb (nur ohne SAP).
"""
from __future__ import annotations

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
                         f"`python -m mockdata.generate` laufen lassen.")
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


def run(count: int, quelle: Path, keep: bool) -> int:
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", type=int, default=200)
    ap.add_argument("--quelle", type=Path, default=Path("mockdata/out"))
    ap.add_argument("--keep", action="store_true",
                    help="Pakete behalten (prüft den Gegenfall)")
    a = ap.parse_args(argv)
    return run(a.count, a.quelle, a.keep)


if __name__ == "__main__":
    sys.exit(main())
