from base import *


def test_load_composition():
    composition = util_load_composition()

    assert len(composition.tracks) == 2


def test_to_sequences():
    composition = util_load_composition()
    sequences = composition.to_sequences()

    assert len(sequences) == 2


def test_save():
    composition = util_load_composition()
    path = Path(__file__).parent.parent / "res" / "out_comp.mid"
    composition.save(path)

    sequences = util_midi_to_sequences(path)
    assert len(sequences) == 2
