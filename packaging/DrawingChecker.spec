# PyInstaller-Spezifikation für die Windows-Auslieferung.
#
#   pip install pyinstaller
#   pyinstaller packaging/DrawingChecker.spec
#
# Ergebnis: dist/DrawingChecker/DrawingChecker.exe (One-Folder – startet
# schneller als One-File und die Wissenspakete liegen sichtbar daneben).
# Anwender-Wissenspakete gehören in einen Ordner `regeln/` NEBEN die .exe.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "drawing_checker" / "app.py")],
    pathex=[str(ROOT)],
    datas=[
        # Mitgelieferte Wissenspakete (YAML)
        (str(ROOT / "drawing_checker" / "rules"), "drawing_checker/rules"),
    ],
    hiddenimports=[
        "drawing_checker.sap.session",
        "drawing_checker.sap.watchdog",
        "win32com", "win32com.client", "win32cred",
    ],
    excludes=["tkinter", "matplotlib", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts,
    exclude_binaries=True,
    name="DrawingChecker",
    console=False,          # GUI-Anwendung ohne Konsolenfenster
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="DrawingChecker")
