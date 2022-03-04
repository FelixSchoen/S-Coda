from abc import ABC, abstractmethod

from sCoda.elements.message import Message


class Sequence(ABC):
    """
    Class representing an abstract musical sequence.
    """

    def __init__(self) -> None:
        super().__init__()
        self.messages = []

    @abstractmethod
    def add_message(self, msg: Message) -> None:
        """Adds a message to the sequence.

        For an `AbsoluteSequence` the message has to contain an entry for `time`, according to which it will
        be sorted into the sequence.

        Args:
            msg: The message to append

        """
        pass
