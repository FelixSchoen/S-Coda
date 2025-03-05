from __future__ import annotations

from abc import ABC, abstractmethod

from scoda.elements.message import Message


class AbstractSequence(ABC):
    """Class representing an abstract musical sequence.

    """

    def __init__(self) -> None:
        super().__init__()
        self._messages = []

    @abstractmethod
    def add_message(self, msg: Message) -> None:
        """Adds a message to the sequence.

        For an `AbsoluteSequence` the message has to contain an entry for `time`, according to which it will
        be sorted into the sequence. This is not needed for a `RelativeSequence`.

        Args:
            msg: The message to append

        """
        pass
