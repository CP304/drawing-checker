"""Der Regelkatalog muss vollständig bleiben.

Neue Regeln ohne Eintrag in REGELKATALOG.md fallen hier auf – damit die
Dokumentation für den Fachbereich nicht hinter dem Code zurückbleibt.
"""
import re
from pathlib import Path

from drawing_checker.checks.base import load_profile, load_profiles_data

KATALOG = Path(__file__).resolve().parent.parent / "REGELKATALOG.md"


def documented_codes() -> set[str]:
    text = KATALOG.read_text(encoding="utf-8")
    return set(re.findall(r"`([A-Z]+\.[A-Z_0-9]+)`", text))


def all_rule_codes() -> set[str]:
    codes: set[str] = set()
    for name in load_profiles_data():
        codes |= set(load_profile(name).rules)
    return codes


def test_every_rule_is_documented():
    missing = sorted(all_rule_codes() - documented_codes())
    assert not missing, f"nicht im Regelkatalog dokumentiert: {missing}"


def test_catalog_has_no_stale_entries():
    """Dokumentierte Codes müssen im Regelwerk existieren."""
    stale = sorted(documented_codes() - all_rule_codes())
    assert not stale, f"im Katalog, aber nicht im Regelwerk: {stale}"


def test_catalog_states_rule_count():
    count = len(load_profile("default").rules)
    assert str(count) in KATALOG.read_text(encoding="utf-8"), (
        f"Regelanzahl im Katalog aktualisieren: aktuell {count}")
