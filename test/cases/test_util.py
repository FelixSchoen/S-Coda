from fixtures import RESOURCE_BEETHOVEN
from s_coda import Composition, Sequence
from util.midi_wrapper import MidiFile


def util_midi_to_sequences(file=None, lead_tracks=None, acmp_tracks=None,
                           meta_tracks=None):
    if file is None:
        file = RESOURCE_BEETHOVEN

    if lead_tracks is None:
        lead_tracks = [1]

    if acmp_tracks is None:
        acmp_tracks = [2]

    if meta_tracks is None:
        meta_tracks = [0, 3]

    midi_file = MidiFile.open_midi_file(file)
    sequences = midi_file.to_sequences([lead_tracks, acmp_tracks], meta_tracks)

    assert len(sequences) == 2

    return sequences


def util_load_composition():
    composition = Composition.from_midi_file(RESOURCE_BEETHOVEN, [[1], [2]], [0, 3])

    assert len(composition.tracks) == 2

    return composition


def util_split_into_bars():
    sequences = util_midi_to_sequences()
    bars = Sequence.split_into_bars(sequences)

    assert len(bars) == 2
    assert len(bars[0]) == len(bars[1])

    return bars
