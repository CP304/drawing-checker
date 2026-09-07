from drawing_checker.regeln import load_profile
from drawing_checker.kern import Severity


def test_default_profile():
    p = load_profile("default")
    assert p.enabled("GT.GENERAL_TOL")
    assert p.severity("GEO.MISMATCH") == Severity.BLOCKER
    assert p.step_tolerance["rel"] == 0.05


def test_guss_inherits_and_overrides():
    p = load_profile("guss")
    # geerbt
    assert p.enabled("LANG.GERMAN")
    assert p.severity("LANG.GERMAN") == Severity.ERROR
    # überschrieben
    assert p.step_tolerance["rel"] == 0.12
    assert p.severity("GEO.MISMATCH") == Severity.WARNING


def test_unknown_profile_falls_back_to_default():
    p = load_profile("gibt_es_nicht")
    assert p.name == "default"


def test_title_block_keywords_configured():
    p = load_profile("default")
    kws = p.rule_param("TB.MATERIAL", "keywords")
    assert "Werkstoff" in kws and "Material" in kws
