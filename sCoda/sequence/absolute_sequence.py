from bisect import insort
from typing import Tuple

from sCoda.elements.message import Message
from sCoda.sequence.sequence import Sequence


class AbsoluteSequence(Sequence):
    """
    Class representing a sequence with absolute message timings.
    """

    def __init__(self) -> None:
        super().__init__()
        self._messages = []

    def add_message(self, msg: Message) -> None:
        insort(self._messages, (msg.time, msg))
