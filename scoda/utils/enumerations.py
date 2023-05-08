from __future__ import annotations

import enum


class NoteRepresentationType(enum.Enum):
    ABSOLUTE_VALUES = 0
    RELATIVE_DISTANCES = 1
    CIRCLE_OF_FIFTHS = 2
    SCALE = 3


class TemporalRepresentationType(enum.Enum):
    RELATIVE_TICKS = 0
    NOTELIKE_REPRESENTATION = 1


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
    RUNNING_TIME_SIG = "running_time_signature"
