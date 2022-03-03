from __future__ import annotations

import enum


class MessageType(enum.Enum):
    note_on = "note_on"
    note_off = "note_off"
    wait = "wait"
    time_signature = "time_signature"
    control_change = "control_change"


class Message:
    """
    Class representing a musical message.
    """

    def __init__(self) -> None:
        super().__init__()
        self.time = None
        self.message_type = None
        self.note = None
        self.velocity = None
        self.control = None
        self.value = None
        self.numerator = None
        self.denominator = None

    @staticmethod
    def gen_note_on(note: int, velocity_unbinned: int, time: int = None) -> Message:
        pass

    @staticmethod
    def gen_time_signature(numerator: int, denominator: int, time: int = None) -> Message:
        msg = Message()
        msg.message_type = MessageType.time_signature
        msg.numerator = numerator
        msg.denominator = denominator

        if time is not None:
            msg.time = time

        return msg

    def __repr__(self) -> str:
        representation = f"{self.message_type.value}:"

        if self.time is not None:
            representation += f" time={self.time}"

        if self.value is not None:
            representation += f" value={self.value}"

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

        return representation


