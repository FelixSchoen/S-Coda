import enum


class Note(enum.Enum):
    c = 0
    c_s = 1
    d = 2
    d_s = 3
    e = 4
    f = 5
    f_s = 6
    g = 7
    g_s = 8
    a = 9
    a_s = 10
    b = 11


class Key(enum.Enum):
    c = "C"
    g = "G"
    d = "D"
    a = "A"
    e = "E"
    b = "B"
    f_s = "F#"
    c_s = "C#"
    f = "F"
    b_b = "Bb"
    e_b = "Eb"
    a_b = "Ab"
    d_b = "Db"
    g_b = "Gb"
    c_b = "Cb"


class CircleOfFifths:
    """Represents knowledge about the circle of fifths, note that some pitches are doubly assigned which can lead to
    ambiguity."""

    circle_of_fifths_order = [Note.c_s, Note.g_s, Note.d_s, Note.a_s, Note.f,
                              Note.c, Note.g, Note.d, Note.a, Note.e, Note.b,
                              Note.f_s]

    @staticmethod
    def get_distance(from_note_val: int, to_note_val: int):
        from_pos = CircleOfFifths.circle_of_fifths_order.index(Note(from_note_val % 12)) - 5
        to_pos = CircleOfFifths.circle_of_fifths_order.index(Note(to_note_val % 12)) - 5

        to_pos = (to_pos - from_pos) % 12
        from_pos = 0

        distance_right = to_pos
        distance_left = 12 - distance_right

        if distance_left == distance_right:
            return distance_right
        elif distance_right < distance_left:
            return distance_right
        else:
            return -distance_left


class MusicMapping:
    KeyKeyMapping = {"C": Key.c, "G": Key.g, "D": Key.d, "A": Key.a, "E": Key.e, "B": Key.b, "F#": Key.f_s,
                     "C#": Key.c_s,
                     "F": Key.f, "Bb": Key.b_b, "Eb": Key.e_b, "Ab": Key.a_b, "Db": Key.d_b, "Gb": Key.g_b,
                     "Cb": Key.c_b,
                     "Am": Key.c, "Em": Key.g, "Bm": Key.d, "F#m": Key.a, "C#m": Key.e, "G#m": Key.b, "D#m": Key.f_s,
                     "Dm": Key.f, "Gm": Key.b_b, "Cm": Key.e_b, "Fm": Key.a_b, "Bbm": Key.d_b, "Ebm": Key.g_b}

    KeyNoteMapping = {
        # Notes belonging to scale, accidentals
        Key.c: ([Note.c, Note.d, Note.e, Note.f, Note.g, Note.a, Note.b], 0),
        Key.g: ([Note.g, Note.a, Note.b, Note.c, Note.d, Note.e, Note.f_s], 1),
        Key.d: ([Note.d, Note.e, Note.f_s, Note.g, Note.a, Note.b, Note.c_s], 2),
        Key.a: ([Note.a, Note.b, Note.c_s, Note.d, Note.e, Note.f_s, Note.g_s], 3),
        Key.e: ([Note.e, Note.f_s, Note.g_s, Note.a, Note.b, Note.c_s, Note.d_s], 4),
        Key.b: ([Note.b, Note.c_s, Note.d_s, Note.e, Note.f_s, Note.g_s, Note.a_s], 5),
        Key.f_s: ([Note.f_s, Note.g_s, Note.a_s, Note.b, Note.c_s, Note.d_s, Note.f], 6),
        Key.c_s: ([Note.c_s, Note.d_s, Note.f, Note.f_s, Note.g_s, Note.a_s, Note.c], 7),
        Key.f: ([Note.f, Note.g, Note.a, Note.a_s, Note.c, Note.d, Note.e], 1),
        Key.b_b: ([Note.a_s, Note.c, Note.d, Note.d_s, Note.f, Note.g, Note.a], 2),
        Key.e_b: ([Note.d_s, Note.f, Note.g, Note.g_s, Note.a_s, Note.c, Note.d], 3),
        Key.a_b: ([Note.g_s, Note.a_s, Note.c, Note.c_s, Note.d_s, Note.f, Note.g], 4),
        Key.d_b: ([Note.c_s, Note.d_s, Note.f, Note.f_s, Note.g_s, Note.a_s, Note.c], 5),
        Key.g_b: ([Note.f_s, Note.g_s, Note.a_s, Note.b, Note.c_s, Note.d_s, Note.f], 6),
        Key.c_b: ([Note.b, Note.c_s, Note.d_s, Note.e, Note.f_s, Note.g_s, Note.a_s], 7)}

    key_transpose_order = [Key.c, Key.c_s, Key.d, Key.e_b, Key.e, Key.f, Key.f_s, Key.g, Key.a_b, Key.a, Key.b_b, Key.b]
    key_transpose_mapping = {Key.d_b: Key.c_s, Key.g_b: Key.f_s, Key.c_b: Key.b}
