from sCoda.elements.message import Message
from sCoda.sequence.sequence import Sequence


class RelativeSequence(Sequence):
    """
    Class representing a sequence with relative message timings.
    """

    def __init__(self) -> None:
        super().__init__()

    def add_message(self, msg: Message) -> None:
        self.messages.append(msg)
