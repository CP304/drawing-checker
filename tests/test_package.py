import zipfile
from pathlib import Path

import pytest

from drawing_checker.kern import ( PackageError, classify_files, extract_package, )


def make_zip(path: Path, names: dict[str, bytes]):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in names.items():
            zf.writestr(name, data)


def test_extract_classifies_content(tmp_path):
    z = tmp_path / "m1.zip"
    make_zip(z, {
        "Z_123.pdf": b"%PDF-1.4 x",
        "M_123.stp": b"ISO-10303-21;",
        "N_123.CATPart": b"native",
    })
    c = extract_package(z, tmp_path / "work", "123")
    assert c.drawing_pdf.name == "Z_123.pdf"
    assert c.step_file.name == "M_123.stp"
    assert len(c.ignored) == 1


def test_zip_slip_names_flattened(tmp_path):
    z = tmp_path / "m2.zip"
    make_zip(z, {"../../evil.pdf": b"x", "sub/dir/ok.pdf": b"y"})
    c = extract_package(z, tmp_path / "work", "m2")
    names = {p.name for p in c.pdfs}
    assert names == {"evil.pdf", "ok.pdf"}
    for p in c.pdfs:
        assert (tmp_path / "work") in p.parents


def test_multi_pdf_prefers_material_in_name(tmp_path):
    a = tmp_path / "Anbau.pdf"; a.write_bytes(b"x" * 500)
    b = tmp_path / "Z_10473215.pdf"; b.write_bytes(b"x" * 100)
    c = classify_files([a, b], "10473215")
    assert c.drawing_pdf.name == "Z_10473215.pdf"


def test_missing_zip_raises(tmp_path):
    with pytest.raises(PackageError):
        extract_package(tmp_path / "fehlt.zip", tmp_path / "w", "x")


def test_empty_zip_raises(tmp_path):
    z = tmp_path / "leer.zip"
    z.write_bytes(b"")
    with pytest.raises(PackageError):
        extract_package(z, tmp_path / "w", "x")


# ------------------------------------------------- Schranke fuers Zusammenlegen
def test_kein_name_wird_im_modul_doppelt_vergeben():
    """Zusammengelegte Module duerfen sich nicht gegenseitig ueberschreiben.

    Beim Flachziehen der Paketstruktur sind zwei verschiedene Regexe unter
    demselben Namen `RE_SCALE` in einem Modul gelandet - der zweite hat den
    ersten verdeckt und die Maßstabserkennung stillgelegt. Gefunden haben
    das die Tests; damit es gar nicht erst passiert, prueft dieser Test
    jedes Modul auf doppelt vergebene Namen auf oberster Ebene.
    """
    import ast
    from collections import Counter
    from pathlib import Path

    wurzel = Path(__file__).resolve().parent.parent / "drawing_checker"
    doppelt = {}
    for pfad in sorted(wurzel.glob("*.py")):
        namen = Counter()
        for knoten in ast.parse(pfad.read_text(encoding="utf-8")).body:
            if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef)):
                namen[knoten.name] += 1
            elif isinstance(knoten, ast.Assign):
                for ziel in knoten.targets:
                    if isinstance(ziel, ast.Name):
                        namen[ziel.id] += 1
        mehrfach = {n: z for n, z in namen.items() if z > 1}
        if mehrfach:
            doppelt[pfad.name] = mehrfach
    assert not doppelt, f"Namen doppelt vergeben: {doppelt}"
