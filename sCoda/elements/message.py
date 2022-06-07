from __future__ import annotations

import enum

from sCoda.util.music_theory import Key


class MessageType(enum.Enum):
    internal = "internal"
    key_signature = "key_signature"
    time_signature = "time_signature"
    control_change = "control_change"
    program_change = "program_change"
    note_off = "note_off"
    note_on = "note_on"
    wait = "wait"

    def __lt__(self, other):
        values = [e for e in MessageType]
        return values.index(self) < values.index(other)


class Message:
    """
    Class representing a musical message.
    """

    def __init__(self, message_type: MessageType = None, note: int = None, velocity: int = None, control: int = None,
                 numerator: int = None, denominator: int = None, key: Key = None, time: int = None,
                 program: int = None) -> None:
        super().__init__()
        self.message_type = message_type
        self.time = time
        self.note = note
        self.velocity = velocity
        self.control = control
        self.program = program
        self.numerator = numerator
        self.denominator = denominator
        self.key = key

    def __copy__(self) -> Message:
        return Message(message_type=self.message_type, note=self.note, velocity=self.velocity, control=self.control,
                       numerator=self.numerator, denominator=self.denominator, key=self.key, time=self.time,
                       program=self.program)

    def __deepcopy__(self, memodict=None) -> Message:
        return self.__copy__()

    def __repr__(self) -> str:
        representation = f"[{self.message_type.value}]:"

        if self.time is not None:
            representation += f" time={self.time}"

        if self.note is not None:
            representation += f" note={self.note}"

        if self.velocity is not None:
            representation += f" velocity={self.velocity}"

        if self.control is not None:
            representation += f" control={self.control}"

        if self.program is not None:
            representation += f" program={self.program}"

        if self.numerator is not None:
            representation += f" numerator={self.numerator}"

        if self.denominator is not None:
            representation += f" denominator={self.denominator}"

        if self.key is not None:
            representation += f" key={self.key.value}"

        return representation

    @staticmethod
    def from_dict(dictionary: dict) -> Message:
        msg = Message(message_type=MessageType[dictionary.get("message_type", None)], note=dictionary.get("note", None),
                      velocity=dictionary.get("velocity", None), control=dictionary.get("control", None),
                      program=dictionary.get("program", None), numerator=dictionary.get("numerator", None),
                      denominator=dictionary.get("denominator", None), key=dictionary.get("key", None),
                      time=dictionary.get("time", None))

        return msg
