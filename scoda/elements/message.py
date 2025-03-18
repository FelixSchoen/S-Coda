from __future__ import annotations

import warnings

from scoda.exceptions.sequence_exception import SequenceException
from scoda.enumerations.message_type import MessageType
from scoda.misc.music_theory import Key


class Message:
    """Class representing a musical message.
    """

    def __init__(self,
                 message_type: MessageType = None,
                 channel: int = None,
                 time: int = None,
                 note: int = None,
                 velocity: int = None,
                 control: int = None,
                 numerator: int = None,
                 denominator: int = None,
                 key: Key = None,
                 program: int = None) -> None:
        super().__init__()
        self.message_type = message_type
        self.channel = channel
        self.time = time
        self.note = note
        self.velocity = velocity
        self.control = control
        self.program = program
        self.numerator = numerator
        self.denominator = denominator
        self.key = key

        # Defaults

        if self.channel is None:
            self.channel = 0

    def equivalent(self, other) -> bool:
        if not isinstance(other, Message):
            return False

        for self_field, other_field in zip(list(self.__dict__.keys()), list(other.__dict__.keys())):
            if not self_field == other_field:
                return False

        return True

    def copy(self) -> Message:
        cpy = self.__class__(
            message_type=self.message_type,
            channel=self.channel,
            time=self.time,
            note=self.note,
            velocity=self.velocity,
            control=self.control,
            program=self.program,
            numerator=self.numerator,
            denominator=self.denominator,
            key=self.key
        )
        return cpy

    def __repr__(self) -> str:
        representation = f"({self.message_type.value}:"

        attributes = [
            ("time", self.time),
            ("channel", self.channel),
            ("note", self.note),
            ("velocity", self.velocity),
            ("control", self.control),
            ("program", self.program),
            ("numerator", self.numerator),
            ("denominator", self.denominator),
            ("key", self.key.value if self.key is not None else None)
        ]

        for attr_name, attr_value in attributes:
            if attr_value is not None:
                representation += f", {attr_name}={attr_value}"

        representation += ")"
        representation = representation.replace(",", "", 1)

        return representation

    @staticmethod
    def from_dict(dictionary: dict) -> Message:
        msg = Message(message_type=MessageType[dictionary.get("message_type", None)],
                      channel=dictionary.get("channel", None),
                      note=dictionary.get("note", None), velocity=dictionary.get("velocity", None),
                      control=dictionary.get("control", None), program=dictionary.get("program", None),
                      numerator=dictionary.get("numerator", None), denominator=dictionary.get("denominator", None),
                      key=dictionary.get("key", None), time=dictionary.get("time", None))

        return msg
