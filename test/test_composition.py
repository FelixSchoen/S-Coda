from sCoda.elements.composition import Composition


def test_create_composition_from_file():
    composition = Composition.from_file("resources/beethoven_o27-2_m3.mid")
    assert True
