from __future__ import annotations

import enum


class MessageType(enum.Enum):
    INTERNAL = "internal"
    SEQUENCE_CONTROL = "sequence_control"
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
