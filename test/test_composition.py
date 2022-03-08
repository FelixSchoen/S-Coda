from sCoda.elements.composition import Composition


def test_create_composition_from_file():
    # composition = Composition.from_file("resources/beethoven_o27-2_m3.mid", [[1], [2]], [0, 3])
    # composition = Composition.from_file("resources/problem_end.mid", [[0]], [0])
    # composition = Composition.from_file("resources/32.mid", [[0]], [0])
    composition = Composition.from_file("resources/triplet.mid", [[0]], [0])
    assert True
