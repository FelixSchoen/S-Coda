from __future__ import annotations

import enum

from sCoda.util.util import digitise_velocity


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

    def __init__(self, message_type: MessageType = None, note: int = None, velocity: int = None, control: int = None,
                 numerator: int = None, denominator: int = None, time: int = None) -> None:
        super().__init__()
        self.time = time
        self.message_type = message_type
        self.note = note
        self.velocity = velocity
        self.control = control
        self.numerator = numerator
        self.denominator = denominator

    @staticmethod
    def gen_note_on(note: int, velocity_unbinned: int, time: int = None) -> Message:
        msg = Message()
        msg.message_type = MessageType.note_on
        msg.note = note
        msg.velocity = digitise_velocity(velocity_unbinned)

        if time is not None:
            msg.time = time

        return msg

    @staticmethod
    def gen_note_off(note: int, time: int = None) -> Message:
        msg = Message()
        msg.message_type = MessageType.note_off
        msg.note = note

        if time is not None:
            msg.time = time

        return msg

    @staticmethod
    def gen_time_signature(numerator: int, denominator: int, time: int = None) -> Message:
        msg = Message()
        msg.message_type = MessageType.time_signature
        msg.numerator = numerator
        msg.denominator = denominator

        if time is not None:
            msg.time = time

        return msg

    @staticmethod
    def gen_control_change(control: int, value: int, time: int = None) -> Message:
        msg = Message()
        msg.message_type = MessageType.control_change
        msg.control = control
        msg.velocity = value

        if time is not None:
            msg.time = time

        return msg

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

        return representation

    def __lt__(self, other):
        message_type_order = [MessageType.note_on, MessageType.note_off, MessageType.wait, MessageType.time_signature,
                              MessageType.control_change]
        return message_type_order.index(self.message_type) < message_type_order.index(other.message_type)
