import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def mock_dir(tmp_path_factory) -> Path:
    """Erzeugt die Mockdaten einmal je Testlauf (Zeichnungen, STEP, ZIPs, Excel)."""
    out = tmp_path_factory.mktemp("mockdaten")
    from mockdata.generate import build_all

    build_all(out)
    return out
