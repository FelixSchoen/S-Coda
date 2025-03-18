from base import *


def test_from_midi_file():
    composition = Composition.from_midi_file(file_path=RESOURCE_BEETHOVEN, track_indices=[[1], [2]],
                                             meta_track_indices=[0, 3])

    assert len(composition.tracks) == 2


def test_to_sequences():
    composition = util_load_composition()
    sequences = composition.to_sequences()

    assert len(sequences) == 2


def test_save():
    composition = util_load_composition()
    path = Path(__file__).parent.parent / "out" / "out_comp.mid"
    path.mkdir(parents=True, exist_ok=True)
    composition.save(path)

    sequences = util_midi_to_sequences(path)
    assert len(sequences) == 2
