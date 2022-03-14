import enum


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


class KeyNoteMapping(enum.Enum):
    Key.c = [Note.c, Note.d, Note.e, Note.f, Note.g, Note.a, Note.b]
    Key.g = [Note.g, Note.a, Note.b, Note.c, Note.d, Note.e, Note.f_s]
    Key.d = [Note.d, Note.e, Note.f_s, Note.g, Note.a, Note.b, Note.c_s]
    Key.a = [Note.a, Note.b, Note.c_s, Note.d, Note.e, Note.f_s, Note.g_s]
    Key.e = [Note.e, Note.f_s, Note.g_s, Note.a, Note.b, Note.c_s, Note.d_s]
    Key.b = [Note.b, Note.c_s, Note.d_s, Note.e, Note.f_s, Note.g_s, Note.a_s]
    Key.f_s = [Note.f_s, Note.g_s, Note.a_s, Note.b, Note.c_s, Note.d_s, Note.f]
    Key.c_s = [Note.c_s, Note.d_s, Note.f, Note.f_s, Note.g_s, Note.a_s, Note.c]
    Key.f = [Note.f, Note.g, Note.a, Note.a_s, Note.c, Note.d, Note.e]
    Key.b_b = [Note.a_s, Note.c, Note.d, Note.d_s, Note.f, Note.g, Note.a]
    Key.e_b = [Note.d_s, Note.f, Note.g, Note.g_s, Note.a_s, Note.c, Note.d]
    Key.a_b = [Note.g_s, Note.a_s, Note.c, Note.c_s, Note.d_s, Note.f, Note.g]
    Key.d_b = [Note.c_s, Note.d_s, Note.f, Note.f_s, Note.g_s, Note.a_s, Note.c]
    Key.g_b = [Note.f_s, Note.g_s, Note.a_s, Note.b, Note.c_s, Note.d_s, Note.f]
    Key.c_b = [Note.b, Note.c_s, Note.d_s, Note.e, Note.f_s, Note.g_s, Note.a_s]


key_accidental_mapping = {

}
