from drawing_checker.checks.language_check import classify_block


def test_pure_german():
    assert classify_block("Alle Kanten gebrochen und entgratet") == "de"
    assert classify_block("Nach dem Schweißen spannungsarm glühen") == "de"


def test_pure_english():
    assert classify_block("All edges broken and deburred") == "en"


def test_bilingual_is_mixed():
    assert classify_block("Maßstab / Scale") == "mixed"
    assert classify_block("Werkstoff / Material") == "mixed"
    assert classify_block("Kanten / Edges: ISO 13715 -0,3") == "mixed"
    assert classify_block(
        "Wärmebehandlung / Heat treatment: vergütet / quenched") == "mixed"


def test_neutral_content():
    assert classify_block("ISO 2768-mK") == "neutral"
    assert classify_block("Ra 3,2") == "neutral"
    assert classify_block("⌀40 H7") == "neutral"
    assert classify_block("42CrMo4 +QT") == "neutral"
