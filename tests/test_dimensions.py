from drawing_checker.kern import BBox
from drawing_checker.zeichnung import ( DimKind, _parse_word, estimate_envelope, extract_dimensions, )
from drawing_checker.zeichnung import Word


def w(text: str) -> Word:
    return Word(text, BBox(0, 0, 10, 10), 0)


def parse(text: str, prev: str = ""):
    return _parse_word(w(text), prev)


def kinds(text: str, prev: str = ""):
    return [(d.kind, d.value) for d in parse(text, prev)]


def test_diameter_variants():
    assert kinds("⌀40") == [(DimKind.DIAMETER, 40.0)]
    assert kinds("Ø22 H11") == [(DimKind.DIAMETER, 22.0)]
    assert kinds("4×⌀18")[0] == (DimKind.DIAMETER, 18.0)


def test_linear_with_tolerances_and_fits():
    assert kinds("420") == [(DimKind.LINEAR, 420.0)]
    assert kinds("120,5") == [(DimKind.LINEAR, 120.5)]
    assert kinds("60±0,2")[0][1] == 60.0
    assert kinds("40H7") == [(DimKind.LINEAR, 40.0)]


def test_radius_and_thread():
    assert kinds("R5") == [(DimKind.RADIUS, 5.0)]
    assert kinds("M12x1,5") == [(DimKind.THREAD, 12.0)]


def test_exclusions():
    assert parse("2768", prev="iso") == []          # Normbezug
    assert parse("1:2") == []                        # Maßstab
    assert parse("10473215") == []                   # Materialnummer
    assert parse("2025") == []                       # Jahr
    assert parse("45°") == []                        # Winkel
    assert parse("12,5kg") == []                     # Gewicht
    assert parse("1/1") == []                        # Blattangabe


def test_envelope_top_values():
    dims = [d for t in ("420", "⌀70", "120", "90", "80", "70", "60", "R3")
            for d in parse(t)]
    env = estimate_envelope(dims)
    assert env[0] == 420.0
    assert 3.0 not in env  # Radius zählt nicht als Hüllmaß


def test_extract_from_real_mock(mock_dir):
    from drawing_checker.zeichnung import DrawingPdf

    with DrawingPdf(mock_dir / "_arbeit" / "Z_10473217.pdf") as pdf:
        dims = extract_dimensions(pdf)
    values = {d.value for d in dims}
    assert 420.0 in values          # Gesamtlänge
    assert 55.0 in values           # ⌀55
    assert 2768.0 not in values     # ISO 2768 nicht als Maß
