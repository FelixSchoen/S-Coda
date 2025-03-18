from __future__ import annotations

from abc import ABC, abstractmethod

from scoda.elements.message import Message


class AbstractSequence(ABC):
    """Class representing an abstract musical sequence.

    """

    def __init__(self, messages: list = None) -> None:
        super().__init__()
        self._messages = []

        if messages is not None:
            self._messages.extend(messages)

    def copy(self) -> AbstractSequence:
        cpy = self.__class__(messages=[msg.copy() for msg in self._messages])
        return cpy

    @abstractmethod
    def add_message(self, msg: Message) -> None:
        """Adds a message to the sequence.

        For an `AbsoluteSequence` the message has to contain an entry for `time`, according to which it will
        be sorted into the sequence. This is not needed for a `RelativeSequence`.

        Args:
            msg: The message to append

        """
        pass
