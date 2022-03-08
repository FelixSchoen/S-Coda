from mido import MidiFile


def test_import_midi_file():
    midi = MidiFile("resources/problem.mid")

    print(midi.ticks_per_beat)

    for i, track in enumerate(midi.tracks):
        print('Track {}: {}'.format(i, track.name))
        time = 0
        for msg in track:
            time += msg.time
            print(f"{msg}, absolute time: {time}")

    assert True