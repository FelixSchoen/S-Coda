from abc import ABC, abstractmethod

from sCoda.elements.message import Message


class Sequence(ABC):
    """
    Class representing an abstract musical sequence.
    """

    @abstractmethod
    def add_message(self, msg: Message) -> None:
        pass
