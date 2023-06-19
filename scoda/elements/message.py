from __future__ import annotations

from scoda.utils.enumerations import MessageType
from scoda.utils.music_theory import Key


class Message:
    """Class representing a musical message.
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

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, Message):
            return False

        is_equal = True

        is_equal &= self.message_type == o.message_type
        is_equal &= self.note == o.note
        is_equal &= self.velocity == o.velocity
        is_equal &= self.control == o.control
        is_equal &= self.numerator == o.numerator
        is_equal &= self.denominator == o.denominator
        is_equal &= self.key == o.key
        is_equal &= self.time == o.time
        is_equal &= self.program == o.program

        return is_equal

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
