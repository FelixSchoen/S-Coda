from sCoda.util.midi_wrapper import MidiFile


def test_midi_to_sequences():
    midi_file = MidiFile.open_midi_file("resources/beethoven_o27-2_m3.mid")
    sequences = midi_file.to_sequences([[1], [2]], [0, 3])

    assert len(sequences) == 2
    return sequences
