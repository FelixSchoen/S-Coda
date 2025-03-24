from __future__ import annotations

from scoda.elements.message import Message
from scoda.enumerations.message_type import MessageType
from scoda.exceptions.bar_exception import BarException
from scoda.misc.music_theory import Key
from scoda.sequences.sequence import Sequence
from scoda.settings.settings import PPQN


class Bar:
    """Class representing a single bar, its length defined by a time signature."""

    def __init__(self, sequence: Sequence, numerator: int, denominator: int, key=None, default_channel=0) -> None:
        super().__init__()

        self.sequence: Sequence = sequence
        self.time_signature_numerator = numerator
        self.time_signature_denominator = denominator
        self.key_signature = key

        # Adjust sequence
        self.sequence.normalise()

        # Assert bar has correct capacity
        if self.sequence.get_sequence_duration_relation() > self.time_signature_numerator * PPQN / (
                self.time_signature_denominator / 4):
            raise BarException("Bar capacity exceeded")

        # Pad bar
        if self.sequence.get_sequence_duration_relation() < self.time_signature_numerator * PPQN / (
                self.time_signature_denominator / 4):
            self.sequence.pad(self.time_signature_numerator * PPQN / (self.time_signature_denominator / 4))

        # Assert time signature is consistent
        time_signatures = [msg for msg in self.sequence.messages_rel() if
                           msg.message_type == MessageType.TIME_SIGNATURE]

        if len(time_signatures) > 1:
            raise BarException("Too many time signatures in a bar")
        if not all(msg.numerator == self.time_signature_numerator and msg.denominator == self.time_signature_denominator
                   for msg in time_signatures):
            raise BarException("Time signatures not uniform")

        # Set time signature and remove all other time signature messages
        self.sequence.overwrite_relative_messages([msg for msg in self.sequence.messages_rel() if
                                                   msg.message_type != MessageType.TIME_SIGNATURE])
        self.sequence.add_relative_message(Message(message_type=MessageType.TIME_SIGNATURE,
                                                   channel=default_channel,
                                                   numerator=self.time_signature_numerator,
                                                   denominator=self.time_signature_denominator), index=0)

        self.sequence._abs_stale = True

    def copy(self) -> Bar:
        cpy = self.__class__(self.sequence.copy(),
                             self.time_signature_numerator, self.time_signature_denominator, self.key_signature)
        return cpy

    def is_empty(self) -> bool:
        return self.sequence.is_empty()

    def transpose(self, transpose_by: int) -> bool:
        """See `scoda.sequence.relative_sequence.RelativeSequence.transpose`.
        """
        if self.key_signature is not None:
            self.key_signature = Key.transpose_key(self.key_signature, transpose_by)

        return self.sequence.transpose(transpose_by)

    @staticmethod
    def to_sequence(bars: [Bar]) -> Sequence:
        sequence = Sequence()
        sequences = []

        for bar in bars:
            sequences.append(bar.sequence)
        sequence.concatenate(sequences)

        return sequence
