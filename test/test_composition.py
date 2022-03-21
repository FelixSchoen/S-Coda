from sCoda.elements.composition import Composition


def test_create_composition_from_file():
    print("Placeholder")
    # composition = Composition.from_file("resources/beethoven_o27-2_m3.mid", [[1], [2]], [0, 3])
    composition = Composition.from_file("resources/beethoven_o27-2_m1.mid", [[1, 2], [3]], [0, 4])
    # composition = Composition.from_file("resources/problem_end.mid", [[0]], [0])
    # composition = Composition.from_file("resources/32.mid", [[0]], [0])
    # composition = Composition.from_file("resources/test_quantisation_64triplet.mid", [[0]], [0])

    # # Testing purposes
    #
    # for i, sequence in enumerate(final_sequences):
    #     track = sequence.to_midi_track()
    #     midi_file = MidiFile()
    #     midi_file.tracks.append(track)
    #     if not os.path.exists("../output"):
    #         os.makedirs("../output")
    #     midi_file.save(f"../output/track_{i}.mid")
    #
    # # Add to composition

    assert True
