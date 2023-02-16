from util import *


def test_track_to_sequence():
    composition = util_load_composition()
    track = composition.tracks[0]
    seq = track.to_sequence()

    assert isinstance(seq, Sequence)
