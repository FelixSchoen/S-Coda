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

    def __init__(self, message_type: MessageType = None, note: int = None, velocity: int = None, control: int = None,
                 numerator: int = None, denominator: int = None, time: int = None) -> None:
        super().__init__()
        self.message_type = message_type
        self.time = time
        self.note = note
        self.velocity = velocity
        self.control = control
        self.numerator = numerator
        self.denominator = denominator

    def __copy__(self) -> Message:
        return Message(message_type=self.message_type, note=self.note, velocity=self.velocity, control=self.control,
                       numerator=self.numerator, denominator=self.denominator, time=self.time)

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

        return representation

    # def __lt__(self, other):
    #     message_type_order = [MessageType.time_signature, MessageType.control_change, MessageType.note_off,
    #                           MessageType.note_on, MessageType.wait]
    #     return message_type_order.index(self.message_type) < message_type_order.index(other.message_type)
