from __future__ import annotations

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
        self._difficulty = None

        if self._sequence.sequence_length() > self._time_signature_numerator * PPQN / (
                self._time_signature_denominator / 4):
            logging.warning("Bar capacity exceeded")
        if self._sequence.sequence_length() < self._time_signature_numerator * PPQN / (
                self._time_signature_denominator / 4):
            self._sequence.pad_sequence(self._time_signature_numerator * PPQN / (self._time_signature_denominator / 4))

    def __copy__(self):
        return Bar(self._sequence.__copy__(), self._time_signature_numerator, self._time_signature_denominator,
                   self._key_signature)

    def difficulty(self) -> float:
        """ See `sCoda.sequence.sequence.Sequence.difficulty`

        """
        return self._sequence.difficulty(key_signature=self._key_signature)

    def get_difficulty(self) -> float:
        if self._difficulty is None:
            self._difficulty = self.difficulty()

        return self._difficulty
