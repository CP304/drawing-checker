"""Massenimport von Normstatus-Daten in das Normen-Wissenspaket.

Konvertiert einen Export der Normenverwaltung (Nautos/Perinorm o. ä.) in
norms-Einträge. Erwartetes CSV (Trennzeichen ; oder ,):

    Dokumentnummer;Status;Nachfolger
    DIN 7168;zurückgezogen;ISO 2768
    ISO 1302;ersetzt;ISO 21920-1
    ISO 13715;gültig;

Nur Zeilen mit Status != gültig werden übernommen. Ausgabe ist eine
YAML-Datei, die als zusätzliches Paket neben norms.yaml gelegt wird
(drawing_checker/rules/norms_firma.yaml) und automatisch mitlädt.

Aufruf:
    python -m tools.import_norms_csv export.csv drawing_checker/rules/norms_firma.yaml
"""
from __future__ import annotations

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
    main = prefixes[-1]
    return rf"(?:DIN\s*)?(?:EN\s*)?{main}\s*{number}\b"


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
             "# (tools/import_norms_csv.py) – manuell nachschärfen erlaubt.",
             "", "obsolete:"]
    for pattern, msg in rows:
        p = pattern.replace("'", "''")
        m = msg.replace("'", "''")
        lines.append(f"  - {{pattern: '{p}',")
        lines.append(f"     message: '{m}'}}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} Einträge -> {out_path}")
    return len(rows)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    convert(Path(sys.argv[1]), Path(sys.argv[2]))
