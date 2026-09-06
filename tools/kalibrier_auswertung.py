"""Wertet einen Kalibrierlauf aus: Fehlalarme vs. gefundene Injektionen.

    python -m mockdata.inject_errors mockdata/echt_quellen /tmp/kal
    python -m drawing_checker.app --headless --mock /tmp/kal \
        --excel /tmp/kal/Materialliste_Echt.xlsx --column C
    python -m tools.kalibrier_auswertung /tmp/kal

Die Referenzpakete (unveränderte Originalzeichnungen) sind der Maßstab für
Fehlalarme: Was dort als Fehler gemeldet wird, ist mit hoher
Wahrscheinlichkeit einer. Die Fehlerpakete zeigen, ob die Injektionen
gefunden werden.
"""
from __future__ import annotations

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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ordner", type=Path)
    return auswerten(ap.parse_args(argv).ordner)


if __name__ == "__main__":
    sys.exit(main())
