from __future__ import annotations

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

    def __copy__(self) -> Message:
        return Message(message_type=self.message_type, channel=self.channel, note=self.note, velocity=self.velocity,
                       control=self.control,
                       numerator=self.numerator, denominator=self.denominator, key=self.key, time=self.time,
                       program=self.program)

    # def __eq__(self, o: object) -> bool:
    #     if not isinstance(o, Message):
    #         return False
    #
    #     return (
    #             self.message_type == o.message_type and
    #             self.note == o.note and
    #             self.velocity == o.velocity and
    #             self.control == o.control and
    #             self.numerator == o.numerator and
    #             self.denominator == o.denominator and
    #             self.key == o.key and
    #             self.time == o.time and
    #             self.program == o.program
    #     )

    # def __hash__(self) -> int:
    #     return hash((
    #         self.message_type,
    #         self.note,
    #         self.velocity,
    #         self.control,
    #         self.numerator,
    #         self.denominator,
    #         self.key,
    #         self.time,
    #         self.program
    #     ))

    def __repr__(self) -> str:
        representation = f"({self.message_type.value}:"

        if self.time is not None:
            representation += f", time={self.time}"

        if self.channel is not None:
            representation += f", channel={self.channel}"

        if self.note is not None:
            representation += f", note={self.note}"

        if self.velocity is not None:
            representation += f", velocity={self.velocity}"

        if self.control is not None:
            representation += f", control={self.control}"

        if self.program is not None:
            representation += f", program={self.program}"

        if self.numerator is not None:
            representation += f", numerator={self.numerator}"

        if self.denominator is not None:
            representation += f", denominator={self.denominator}"

        if self.key is not None:
            representation += f", key={self.key.value}"

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
