from mido import MidiFile


def test_import_midi_file():
    midi = MidiFile("resources/albeniz_sEspanola_aragon.mid")

    print(midi.ticks_per_beat)

    for i, track in enumerate(midi.tracks):
        for msg in track:
            if msg.type == "key_signature":
                print(msg)

    assert True