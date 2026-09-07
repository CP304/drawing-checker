"""Zugriff auf die echten Kalibrierzeichnungen.

Die 84 Fremdzeichnungen (plus STEP-Modelle) liegen als EIN Archiv im
Repository – `mockdata/echt_quellen.zip`. Grund: Als Einzeldateien waren
es über hundert Einträge, die jede Dateiliste zumüllen und beim
Weitergeben stören. Wer sie braucht, bekommt sie hier ausgepackt; das
Auspacken passiert einmalig in einen Cache-Ordner, der nicht im
Repository liegt.

    from mockdata.quellen import zeichnungen

    ordner = zeichnungen()      # Path auf den ausgepackten Ordner

Herkunft und Lizenzen: mockdata/echt_quellen/SOURCES.md
"""
from __future__ import annotations

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


if __name__ == "__main__":
    ordner = zeichnungen()
    pdf, step = anzahl()
    print(f"{pdf} Zeichnungen, {step} STEP-Modelle ausgepackt nach:")
    print(f"  {ordner}")
