# Mido
import mido


def test_wip_print_midi_file():
    midi_file = mido.MidiFile()

    for track in midi_file.tracks:
        print()
        print("new track")
        for msg in track:
            print(msg)

    print(len(midi_file.tracks))
