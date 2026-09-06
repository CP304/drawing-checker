"""Baut EINE ZIP-Datei zum Verteilen auf den Anwenderrechner.

Hintergrund: Der Zielrechner bekommt die Dateien über einen Kanal mit
Begrenzung der Dateianzahl. Deshalb geht alles in ein einziges Archiv –
entpacken, `Start.bat` doppelklicken, fertig.

    python -m tools.paket_bauen [--ziel dist] [--mit-tests]

Enthalten ist alles, was am Zielrechner gebraucht wird: das Programm samt
Wissenspaketen, das Startskript, die Anleitungen. NICHT enthalten sind die
Kalibrierzeichnungen (25 MB Testmaterial), Entwicklungsdateien und alles,
was sich am Zielrechner ohnehin neu bildet (virtuelle Umgebung, Caches).

Das Archiv wird nach dem Bauen selbst geprüft: Sind alle Pflichtdateien
drin, ist Start.bat auf oberster Ebene, lässt sich das Programm aus dem
entpackten Stand heraus importieren?
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
# Alles liegt im Archiv unter EINEM Ordner. Dann landet beim Entpacken
# nichts verstreut im Zielordner, egal welche Variante der Anwender waehlt.
ORDNER_IM_ARCHIV = "DrawingChecker"

# Was ins Paket gehört. Reihenfolge = Reihenfolge im Archiv.
PFLICHT_DATEIEN = [
    "Start.bat",
    "LIESMICH.txt",
    "pyproject.toml",
    "ANLEITUNG.md",
    "SAP_DURCHSTICH.md",
    "REGELKATALOG.md",
    "KNOWHOW.md",
]
ORDNER = ["drawing_checker"]
ORDNER_MIT_TESTS = ["drawing_checker", "tests", "mockdata"]

# Diese Muster fliegen raus (Caches, Entwicklungsreste, Testmaterial).
AUSSCHLUSS = (
    "__pycache__", ".pyc", ".pyo", ".pytest_cache", ".git",
    "echt_quellen", "mockdata/out", "Ergebnisse", ".venv", "logs/",
)


def gehoert_dazu(pfad: Path) -> bool:
    text = pfad.as_posix()
    return not any(muster in text for muster in AUSSCHLUSS)


def sammle(mit_tests: bool) -> list[tuple[Path, str]]:
    """(Quelldatei, Name im Archiv) für alles, was mitkommt."""
    dateien: list[tuple[Path, str]] = []
    for name in PFLICHT_DATEIEN:
        quelle = WURZEL / name
        if not quelle.is_file():
            raise SystemExit(f"Pflichtdatei fehlt: {name}")
        dateien.append((quelle, name))
    for ordner in (ORDNER_MIT_TESTS if mit_tests else ORDNER):
        basis = WURZEL / ordner
        if not basis.is_dir():
            continue
        for pfad in sorted(basis.rglob("*")):
            if pfad.is_file() and gehoert_dazu(pfad.relative_to(WURZEL)):
                dateien.append((pfad, pfad.relative_to(WURZEL).as_posix()))
    return dateien


def bauen(ziel_dir: Path, mit_tests: bool) -> Path:
    dateien = sammle(mit_tests)
    ziel_dir.mkdir(parents=True, exist_ok=True)
    ziel = ziel_dir / "DrawingChecker.zip"
    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for quelle, name in dateien:
            zf.write(quelle, f"{ORDNER_IM_ARCHIV}/{name}")
    return ziel


def pruefen(archiv: Path) -> list[str]:
    """Das gebaute Archiv gegenprüfen – lieber hier scheitern als morgen."""
    probleme: list[str] = []
    with zipfile.ZipFile(archiv) as zf:
        namen = set(zf.namelist())
        kaputt = zf.testzip()
    if kaputt:
        probleme.append(f"Archiv beschädigt bei {kaputt}")
    for kurz in ("Start.bat", "LIESMICH.txt", "pyproject.toml",
                 "drawing_checker/app.py",
                 "drawing_checker/rules/profiles.yaml",
                 "drawing_checker/rules/materials.yaml",
                 "drawing_checker/rules/norms.yaml",
                 "drawing_checker/rules/beschaffung.yaml"):
        pflicht = f"{ORDNER_IM_ARCHIV}/{kurz}"
        if pflicht not in namen:
            probleme.append(f"fehlt im Archiv: {pflicht}")
    if any(n.startswith(("/", "\\")) or ".." in n for n in namen):
        probleme.append("verdächtige Pfade im Archiv")
    if any("__pycache__" in n or n.endswith(".pyc") for n in namen):
        probleme.append("Cache-Dateien im Archiv")

    # Entpacken und das Programm ohne Installation importieren:
    # findet fehlende Wissenspakete und Tippfehler in den YAML-Dateien.
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(archiv) as zf:
            zf.extractall(tmp)
        ergebnis = subprocess.run(
            [sys.executable, "-m", "drawing_checker.app", "--check-rules"],
            cwd=Path(tmp) / ORDNER_IM_ARCHIV, capture_output=True, text=True)
        if ergebnis.returncode != 0:
            probleme.append("Regelprüfung im entpackten Stand fehlgeschlagen: "
                            + (ergebnis.stdout + ergebnis.stderr)[-400:])
        elif "in Ordnung" not in ergebnis.stdout:
            probleme.append("Regelprüfung meldet Probleme:\n"
                            + ergebnis.stdout[-400:])
    return probleme


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ziel", type=Path, default=WURZEL / "dist")
    ap.add_argument("--mit-tests", action="store_true",
                    help="Tests und Mockdaten mitpacken (für den Selbsttest "
                         "am Zielrechner)")
    a = ap.parse_args(argv)

    if shutil.which("git"):
        stand = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                               cwd=WURZEL, capture_output=True, text=True)
        if stand.returncode == 0:
            print(f"Stand: {stand.stdout.strip()}")

    archiv = bauen(a.ziel, a.mit_tests)
    groesse = archiv.stat().st_size / (1024 * 1024)
    with zipfile.ZipFile(archiv) as zf:
        anzahl = len(zf.namelist())
    print(f"Gebaut: {archiv}  ({groesse:.1f} MB, {anzahl} Dateien im Archiv)")

    probleme = pruefen(archiv)
    if probleme:
        print("\nPROBLEME:")
        for p in probleme:
            print(f"  - {p}")
        return 1
    print("Archiv geprüft: vollständig, entpackbar, Regeln laden sauber.")
    print("\nWeitergabe: diese eine ZIP-Datei übertragen. Am Zielrechner")
    print("entpacken (es entsteht der Ordner DrawingChecker) und darin")
    print("Start.bat doppelklicken. Alles Weitere macht das Skript.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
