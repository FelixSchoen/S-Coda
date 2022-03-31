from sCoda import Sequence
from sCoda.elements.composition import Composition


def test_create_composition_from_file():
    print("Placeholder")
    # composition = Composition.from_file("resources/beethoven_o27-2_m3.mid", [[1], [2]], [0, 3])
    # composition = Composition.from_file("resources/beethoven_o27-2_m1.mid", [[1, 2], [3]], [0, 4])
    # composition = Composition.from_file("resources/problem_end.mid", [[0]], [0])
    # composition = Composition.from_file("resources/32.mid", [[0]], [0])
    # composition = Composition.from_file("resources/test_quantisation_64triplet.mid", [[0]], [0])
    # composition = Composition.from_file("resources/albeniz_sEspanola_aragon.mid", [[1], [2]], [0])
    composition = Composition.from_file("resources/liszt_hungarian_rhapsodies_n10.mid", [[1], [2]], [0, 3])

    for i, bar in enumerate(composition.tracks[0].bars):
        print(f"Bar {i+1}")
        bar.set_difficulty()


    assert True
