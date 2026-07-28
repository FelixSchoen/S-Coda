"""Small, typed music-theory primitives used by S-Coda."""

from __future__ import annotations

from enum import StrEnum

from scoda.errors import ValidationError


class Key(StrEnum):
    """A standard MIDI major or minor key signature.

    Enum values use the spellings accepted by MIDI files. Enharmonic keys are
    preserved when parsed, while transposition returns one canonical spelling
    for each pitch class and mode.
    """

    C = "C"
    G = "G"
    D = "D"
    A = "A"
    E = "E"
    B = "B"
    F_SHARP = "F#"
    C_SHARP = "C#"
    F = "F"
    B_FLAT = "Bb"
    E_FLAT = "Eb"
    A_FLAT = "Ab"
    D_FLAT = "Db"
    G_FLAT = "Gb"
    C_FLAT = "Cb"
    A_MINOR = "Am"
    E_MINOR = "Em"
    B_MINOR = "Bm"
    F_SHARP_MINOR = "F#m"
    C_SHARP_MINOR = "C#m"
    G_SHARP_MINOR = "G#m"
    D_SHARP_MINOR = "D#m"
    A_SHARP_MINOR = "A#m"
    D_MINOR = "Dm"
    G_MINOR = "Gm"
    C_MINOR = "Cm"
    F_MINOR = "Fm"
    B_FLAT_MINOR = "Bbm"
    E_FLAT_MINOR = "Ebm"
    A_FLAT_MINOR = "Abm"

    def transpose(self, semitones: int) -> Key:
        """Return this key transposed by ``semitones`` without changing mode."""

        if isinstance(semitones, bool) or not isinstance(semitones, int):
            raise ValidationError("semitones must be an integer")
        canonical = _CANONICAL_EQUIVALENTS.get(self, self)
        order = _MINOR_TRANSPOSE_ORDER if canonical.value.endswith("m") else _MAJOR_TRANSPOSE_ORDER
        return order[(order.index(canonical) + semitones) % 12]


_MAJOR_TRANSPOSE_ORDER = (
    Key.C,
    Key.C_SHARP,
    Key.D,
    Key.E_FLAT,
    Key.E,
    Key.F,
    Key.F_SHARP,
    Key.G,
    Key.A_FLAT,
    Key.A,
    Key.B_FLAT,
    Key.B,
)

_MINOR_TRANSPOSE_ORDER = (
    Key.C_MINOR,
    Key.C_SHARP_MINOR,
    Key.D_MINOR,
    Key.E_FLAT_MINOR,
    Key.E_MINOR,
    Key.F_MINOR,
    Key.F_SHARP_MINOR,
    Key.G_MINOR,
    Key.A_FLAT_MINOR,
    Key.A_MINOR,
    Key.B_FLAT_MINOR,
    Key.B_MINOR,
)

_CANONICAL_EQUIVALENTS = {
    Key.D_FLAT: Key.C_SHARP,
    Key.G_FLAT: Key.F_SHARP,
    Key.C_FLAT: Key.B,
    Key.A_SHARP_MINOR: Key.B_FLAT_MINOR,
    Key.D_SHARP_MINOR: Key.E_FLAT_MINOR,
    Key.G_SHARP_MINOR: Key.A_FLAT_MINOR,
}

_CIRCLE_OF_FIFTHS = (1, 8, 3, 10, 5, 0, 7, 2, 9, 4, 11, 6)


def _circle_of_fifths_position(pitch: int) -> int:
    """Return the signed circle-of-fifths position of a MIDI pitch class."""

    return _CIRCLE_OF_FIFTHS.index(pitch % 12) - 5
