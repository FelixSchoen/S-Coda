import copy

from sCoda.elements.composition import Composition


def test_create_composition_from_file():
    print("Placeholder")
    # composition = Composition.from_file("resources/beethoven_o27-2_m3.mid", [[1], [2]], [0, 3])
    # composition = Composition.from_file("resources/beethoven_o27-2_m1.mid", [[1, 2], [3]], [0, 4])
    # composition = Composition.from_file("resources/problem_end.mid", [[0]], [0])
    # composition = Composition.from_file("resources/32.mid", [[0]], [0])
    # composition = Composition.from_file("resources/test_quantisation_64triplet.mid", [[0]], [0])
    # composition = Composition.from_file("resources/albeniz_sEspanola_aragon.mid", [[1], [2]], [0])
    # composition = Composition.from_file("resources/liszt_hungarian_rhapsodies_n10.mid", [[1], [2]], [0, 3])
    composition = Composition.from_file("resources/albeniz_op165_caprichocatalan.mid", [[1], [2]], [0])

    for i, bar in enumerate(composition.tracks[0].bars):
        if i < 2:
            continue

        print("Starting new bar")

        seq = copy.copy(bar._sequence._get_rel())

        valid_messages = []

        for j in range(1, len(seq.messages)+1):
            asdf = copy.copy(seq)
            asdf.messages = asdf.messages[:j]
            print(f"New message: {asdf.messages[-1]}")

            valid_now = asdf.get_valid_next_messages(desired_bars=2)
            added = [msg for msg in valid_now if msg not in valid_messages]
            removed = [msg for msg in valid_messages if msg not in valid_now]
            valid_messages = valid_now

            print(f"Added: {added}")
            print(f"Removed: {removed}")
            print(f"Valid messages: {len(valid_messages)}")

        break
