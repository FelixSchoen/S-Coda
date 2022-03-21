import logging

from sCoda.sequence.sequence import Sequence
from sCoda.settings import PPQN


class Bar:
    """
    Class representing a single bar, its length defined by a time signature.
    """

    def __init__(self, sequence: Sequence, numerator: int, denominator: int, key=None) -> None:
        super().__init__()
        self._sequence: Sequence = sequence
        self._time_signature_numerator = numerator
        self._time_signature_denominator = denominator
        self._key_signature = key

        if len(sequence._get_abs().messages) > 0 and sequence._get_abs().messages[-1].time > \
                self._time_signature_numerator * PPQN / (self._time_signature_denominator / 4):
            logging.warning("Bar capacity exceeded")

    def difficulty(self) -> float:
        """ See `sCoda.sequence.sequence.Sequence.difficulty`

        """
        return self._sequence.difficulty(key_signature=self._key_signature)


