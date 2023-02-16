from pathlib import Path

import pytest

RESOURCES_ROOT = Path(__file__).parent.parent / "resources"
RESOURCE_BEETHOVEN = str(RESOURCES_ROOT / "beethoven_o27-2_m3.mid")
RESOURCE_CHOPIN = str(RESOURCES_ROOT / "chopin_o66_fantaisie_impromptu.mid")

@pytest.fixture
def resource_beethoven():
    return str(RESOURCES_ROOT / "beethoven_o27-2_m3.mid")


@pytest.fixture()
def resource_chopin():
    return str(RESOURCES_ROOT / "chopin_o66_fantaisie_impromptu.mid")
