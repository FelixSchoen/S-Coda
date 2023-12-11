from __future__ import annotations

import enum


class TokeniserType(enum.Enum):
    MIDILIKE_TOKENISER = "midilike_tokeniser"
    STANDARD_NOTELIKE_TOKENISER = "standard_notelike_tokeniser"
    COF_NOTELIKE_TOKENISER = "cof_notelike_tokeniser"
    LARGE_DICTIONARY_NOTELIKE_TOKENISER = "large_dictionary_notelike_tokeniser"
    GRIDLIKE_TOKENISER = "gridlike_tokeniser"
    TRANSPOSED_NOTELIKE_TOKENISER = "transposed_notelike_tokeniser"


class MessageType(enum.Enum):
    INTERNAL = "internal"
    KEY_SIGNATURE = "key_signature"
    TIME_SIGNATURE = "time_signature"
    CONTROL_CHANGE = "control_change"
    PROGRAM_CHANGE = "program_change"
    NOTE_OFF = "note_off"
    NOTE_ON = "note_on"
    WAIT = "wait"

    def __lt__(self, other):
        values = [e for e in MessageType]
        return values.index(self) < values.index(other)


class Flags(enum.Enum):
    RUNNING_VALUE = "running_value"
    RUNNING_PITCH = "running_pitch"
    RUNNING_OCTAVE = "running_octave"
    RUNNING_TIME_SIG = "running_time_signature"
