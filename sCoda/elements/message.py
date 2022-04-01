from __future__ import annotations

import enum

from sCoda.util.music_theory import Key


class MessageType(enum.Enum):
    internal = "internal"
    note_on = "note_on"
    note_off = "note_off"
    wait = "wait"
    time_signature = "time_signature"
    control_change = "control_change"
    key_signature = "key_signature"


class Message:
    """
    Class representing a musical message.
    """

    def __init__(self, message_type: MessageType = None, note: int = None, velocity: int = None, control: int = None,
                 numerator: int = None, denominator: int = None, key: Key = None, time: int = None) -> None:
        super().__init__()
        self.message_type = message_type
        self.time = time
        self.note = note
        self.velocity = velocity
        self.control = control
        self.numerator = numerator
        self.denominator = denominator
        self.key = key

    def __copy__(self) -> Message:
        return Message(message_type=self.message_type, note=self.note, velocity=self.velocity, control=self.control,
                       numerator=self.numerator, denominator=self.denominator, key=self.key, time=self.time)

    def __deepcopy__(self, memodict=None) -> Message:
        return self.__copy__()

    def __repr__(self) -> str:
        representation = f"{self.message_type.value}:"

        if self.time is not None:
            representation += f" time={self.time}"

        if self.note is not None:
            representation += f" note={self.note}"

        if self.velocity is not None:
            representation += f" velocity={self.velocity}"

        if self.control is not None:
            representation += f" control={self.control}"

        if self.numerator is not None:
            representation += f" numerator={self.numerator}"

        if self.denominator is not None:
            representation += f" denominator={self.denominator}"

        if self.key is not None:
            representation += f" key={self.key.value}"

        return representation
