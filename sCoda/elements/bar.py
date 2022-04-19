from __future__ import annotations

import logging

from pandas import DataFrame

from sCoda.elements.message import MessageType, Message
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

        # Assert bar has correct capacity
        if self._sequence.sequence_length() > self._time_signature_numerator * PPQN / (
                self._time_signature_denominator / 4):
            logging.warning("Bar capacity exceeded")
            assert False

        # Pad bar
        if self._sequence.sequence_length() < self._time_signature_numerator * PPQN / (
                self._time_signature_denominator / 4):
            self._sequence.pad_sequence(self._time_signature_numerator * PPQN / (self._time_signature_denominator / 4))

        # Set time signature
        relative_sequence = self._sequence._get_rel()
        relative_sequence.messages = [msg for msg in relative_sequence.messages if
                                      msg.message_type != MessageType.time_signature]
        relative_sequence.messages.insert(0, Message(message_type=MessageType.time_signature,
                                                     numerator=self._time_signature_numerator,
                                                     denominator=self._time_signature_denominator))
        self._sequence._abs_stale = True

    def __copy__(self):
        bar = Bar(self._sequence.__copy__(), self._time_signature_numerator, self._time_signature_denominator,
                  self._key_signature)
        bar._difficulty = self._difficulty

        return bar

    @property
    def difficulty(self) -> float:
        if self._difficulty is None:
            self.set_difficulty()

        return self._difficulty

    def calculate_difficulty(self) -> float:
        """ See `sCoda.sequence.sequence.Sequence.difficulty`

        """
        return self._sequence.difficulty(key_signature=self._key_signature)

    def set_difficulty(self) -> None:
        """ Calculates and assigns the difficulty of this bar

        """
        self._difficulty = self.calculate_difficulty()

    def to_absolute_dataframe(self) -> DataFrame:
        """ See `sCoda.sequence.sequence.Sequence.to_absolute_dataframe`

        """
        return self._sequence.to_absolute_dataframe()

    def to_relative_dataframe(self) -> DataFrame:
        """ See `sCoda.sequence.sequence.Sequence.to_relative_dataframe`

        """
        return self._sequence.to_relative_dataframe()

    def transpose(self, transpose_by: int) -> bool:
        """ See `sCoda.sequence.relative_sequence.RelativeSequence.transpose`

        """
        return self._sequence.transpose(transpose_by)
