import enum


class Note(enum.Enum):
    C = 0
    C_S = 1
    D = 2
    D_S = 3
    E = 4
    F = 5
    F_S = 6
    G = 7
    G_S = 8
    A = 9
    A_S = 10
    B = 11


class Key(enum.Enum):
    C = "C"
    G = "G"
    D = "D"
    A = "A"
    E = "E"
    B = "B"
    F_S = "F#"
    C_S = "C#"
    F = "F"
    B_B = "Bb"
    E_B = "Eb"
    A_B = "Ab"
    D_B = "Db"
    G_B = "Gb"
    C_B = "Cb"

    @staticmethod
    def transpose_key(key, transpose_by):
        if transpose_by % 12 != 0:
            if key in MusicMapping.key_transpose_mapping:
                key = MusicMapping.key_transpose_mapping[key]

            index = MusicMapping.key_transpose_order.index(key)
            index = (index + transpose_by) % 12
            return MusicMapping.key_transpose_order[index]


class CircleOfFifths:
    """Represents knowledge about the circle of fifths, note that some pitches are doubly assigned which can lead to
    ambiguity."""

    circle_of_fifths_order = [Note.C_S, Note.G_S, Note.D_S, Note.A_S, Note.F,
                              Note.C, Note.G, Note.D, Note.A, Note.E, Note.B,
                              Note.F_S]

    @staticmethod
    def get_position(note_val: int):
        return CircleOfFifths.circle_of_fifths_order.index(Note(note_val % 12)) - 5

    @staticmethod
    def get_distance(from_note_val: int, to_note_val: int):
        from_pos = CircleOfFifths.get_position(from_note_val)
        to_pos = CircleOfFifths.get_position(to_note_val)

        distance_right = (to_pos - from_pos) % 12
        distance_left = 12 - distance_right

        if distance_left == distance_right:
            distance = distance_right
        elif distance_right < distance_left:
            distance = distance_right
        else:
            distance = -distance_left

        assert -5 <= distance <= 6

        return distance

    @staticmethod
    def from_distance(base_note_val: int, cof_distance: int):
        base_pos = CircleOfFifths.circle_of_fifths_order.index(Note(base_note_val % 12))
        return CircleOfFifths.circle_of_fifths_order[(base_pos + cof_distance) % 12].value


class MusicMapping:
    KeyKeyMapping = {"C": Key.C, "G": Key.G, "D": Key.D, "A": Key.A, "E": Key.E, "B": Key.B, "F#": Key.F_S,
                     "C#": Key.C_S,
                     "F": Key.F, "Bb": Key.B_B, "Eb": Key.E_B, "Ab": Key.A_B, "Db": Key.D_B, "Gb": Key.G_B,
                     "Cb": Key.C_B,
                     "Am": Key.C, "Em": Key.G, "Bm": Key.D, "F#m": Key.A, "C#m": Key.E, "G#m": Key.B, "D#m": Key.F_S,
                     "Dm": Key.F, "Gm": Key.B_B, "Cm": Key.E_B, "Fm": Key.A_B, "Bbm": Key.D_B, "Ebm": Key.G_B}

    KeyNoteMapping = {
        # Notes belonging to scale, accidentals
        Key.C: ([Note.C, Note.D, Note.E, Note.F, Note.G, Note.A, Note.B], 0),
        Key.G: ([Note.G, Note.A, Note.B, Note.C, Note.D, Note.E, Note.F_S], 1),
        Key.D: ([Note.D, Note.E, Note.F_S, Note.G, Note.A, Note.B, Note.C_S], 2),
        Key.A: ([Note.A, Note.B, Note.C_S, Note.D, Note.E, Note.F_S, Note.G_S], 3),
        Key.E: ([Note.E, Note.F_S, Note.G_S, Note.A, Note.B, Note.C_S, Note.D_S], 4),
        Key.B: ([Note.B, Note.C_S, Note.D_S, Note.E, Note.F_S, Note.G_S, Note.A_S], 5),
        Key.F_S: ([Note.F_S, Note.G_S, Note.A_S, Note.B, Note.C_S, Note.D_S, Note.F], 6),
        Key.C_S: ([Note.C_S, Note.D_S, Note.F, Note.F_S, Note.G_S, Note.A_S, Note.C], 7),
        Key.F: ([Note.F, Note.G, Note.A, Note.A_S, Note.C, Note.D, Note.E], 1),
        Key.B_B: ([Note.A_S, Note.C, Note.D, Note.D_S, Note.F, Note.G, Note.A], 2),
        Key.E_B: ([Note.D_S, Note.F, Note.G, Note.G_S, Note.A_S, Note.C, Note.D], 3),
        Key.A_B: ([Note.G_S, Note.A_S, Note.C, Note.C_S, Note.D_S, Note.F, Note.G], 4),
        Key.D_B: ([Note.C_S, Note.D_S, Note.F, Note.F_S, Note.G_S, Note.A_S, Note.C], 5),
        Key.G_B: ([Note.F_S, Note.G_S, Note.A_S, Note.B, Note.C_S, Note.D_S, Note.F], 6),
        Key.C_B: ([Note.B, Note.C_S, Note.D_S, Note.E, Note.F_S, Note.G_S, Note.A_S], 7)}

    key_transpose_order = [Key.C, Key.C_S, Key.D, Key.E_B, Key.E, Key.F, Key.F_S, Key.G, Key.A_B, Key.A, Key.B_B, Key.B]
    key_transpose_mapping = {Key.D_B: Key.C_S, Key.G_B: Key.F_S, Key.C_B: Key.B}
