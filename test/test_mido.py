from mido import MidiFile


def test_import_midi_file():
    midi = MidiFile("resources/beethoven_o27-2_m3.mid")

    for i, track in enumerate(midi.tracks):
        print('Track {}: {}'.format(i, track.name))
        for msg in track:
            if msg.type != "note_on" and msg.type != "set_tempo":
                print(msg)

    assert True
