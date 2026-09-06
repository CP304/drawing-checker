import zipfile
from pathlib import Path

import pytest

from drawing_checker.core.package import (
    PackageError, classify_files, extract_package,
)


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
