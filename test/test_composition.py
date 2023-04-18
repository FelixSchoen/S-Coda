from base import *


def test_load_composition():
    composition = util_load_composition()

    assert len(composition.tracks) == 2
