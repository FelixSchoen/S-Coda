from base import *


def test_circle_of_fifths_distance():
    assert CircleOfFifths.get_distance(Note.c.value, Note.g.value) == 1
    assert CircleOfFifths.get_distance(Note.c.value, Note.f.value) == -1

    assert CircleOfFifths.get_distance(Note.b.value, Note.f_s.value) == 1
    assert CircleOfFifths.get_distance(Note.c_s.value, Note.f_s.value) == -1

    assert CircleOfFifths.get_distance(Note.c.value, Note.f_s.value) == 6
    assert CircleOfFifths.get_distance(Note.f_s.value, Note.c.value) == 6

    assert CircleOfFifths.get_distance(Note.a.value, Note.d_s.value) == 6
    assert CircleOfFifths.get_distance(Note.d_s.value, Note.e.value) == -5

    assert CircleOfFifths.get_distance(Note.c.value, Note.f_s.value) == 6
    assert CircleOfFifths.get_distance(Note.f_s.value, Note.c.value) == 6

    assert CircleOfFifths.get_distance(Note.f_s.value, Note.g_s.value) == 2
    assert CircleOfFifths.get_distance(Note.f_s.value, Note.e.value) == -2

    assert CircleOfFifths.get_distance(Note.f_s.value, Note.f.value) == 5
    assert CircleOfFifths.get_distance(Note.f_s.value, Note.g.value) == -5
