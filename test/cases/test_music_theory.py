from base import *


def test_circle_of_fifths_get_distance():
    assert CircleOfFifths.get_distance(Note.C.value, Note.G.value) == 1
    assert CircleOfFifths.get_distance(Note.C.value, Note.F.value) == -1

    assert CircleOfFifths.get_distance(Note.B.value, Note.F_S.value) == 1
    assert CircleOfFifths.get_distance(Note.C_S.value, Note.F_S.value) == -1

    assert CircleOfFifths.get_distance(Note.C.value, Note.F_S.value) == 6
    assert CircleOfFifths.get_distance(Note.F_S.value, Note.C.value) == 6

    assert CircleOfFifths.get_distance(Note.A.value, Note.D_S.value) == 6
    assert CircleOfFifths.get_distance(Note.D_S.value, Note.E.value) == -5

    assert CircleOfFifths.get_distance(Note.C.value, Note.F_S.value) == 6
    assert CircleOfFifths.get_distance(Note.F_S.value, Note.C.value) == 6

    assert CircleOfFifths.get_distance(Note.F_S.value, Note.G_S.value) == 2
    assert CircleOfFifths.get_distance(Note.F_S.value, Note.E.value) == -2

    assert CircleOfFifths.get_distance(Note.F_S.value, Note.F.value) == 5
    assert CircleOfFifths.get_distance(Note.F_S.value, Note.G.value) == -5


def test_circle_of_fifths_from_distance():
    assert CircleOfFifths.from_distance(24, 1) == Note.G.value
    assert CircleOfFifths.from_distance(31, -1) == Note.C.value

    assert CircleOfFifths.from_distance(69, 5) == Note.G_S.value
    assert CircleOfFifths.from_distance(80, -5) == Note.A.value

    assert CircleOfFifths.from_distance(66, -4) == Note.D.value
    assert CircleOfFifths.from_distance(74, 4) == Note.F_S.value
