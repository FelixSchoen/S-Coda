from __future__ import annotations

from sCoda.sequence.absolute_sequence import AbsoluteSequence
from sCoda.sequence.relative_sequence import RelativeSequence
from sCoda.settings import PPQN
from sCoda.util.midi_wrapper import MidiTrack


class Sequence:
    """ Wrapper for `sCoda.sequence.absolute_sequence.AbsoluteSequence` and
    `sCoda.sequence.relative_sequence.RelativeSequence`.

    This class serves as a wrapper for the two above-mentioned classes. This abstraction provides an easier
    understanding for the end-user, who does not have to concern themselves with implementational details.
    """

    def __init__(self, absolute_sequence: AbsoluteSequence = None, relative_sequence: RelativeSequence = None) -> None:
        super().__init__()
        self._abs_stale = True
        self._rel_stale = True
        if absolute_sequence is None:
            self._abs = AbsoluteSequence()
        else:
            self._abs = absolute_sequence
            self._abs_stale = False
        if relative_sequence is None:
            self._rel = RelativeSequence()
        else:
            self._rel = relative_sequence
            self._rel_stale = False

    def _get_abs(self) -> AbsoluteSequence:
        if self._abs_stale:
            self._abs_stale = False
            self._abs = self._rel.to_absolute_sequence()
        return self._abs

    def _get_rel(self) -> RelativeSequence:
        if self._rel_stale:
            self._rel_stale = False
            self._rel = self._abs.to_relative_sequence()
        return self._rel

    def add_absolute_message(self, msg) -> None:
        """ See `sCoda.sequence.absolute_sequence.AbsoluteSequence.add_message`

        """
        self._get_abs().add_message(msg)

    def add_relative_message(self, msg) -> None:
        """ See `sCoda.sequence.relative_sequence.RelativeSequence.add_message`

        """
        self._get_rel().add_message(msg)

    def adjust_wait_messages(self) -> None:
        """ See `sCoda.sequence.relative_sequence.RelativeSequence.adjust_wait_messages`

        """
        self._get_rel().adjust_wait_messages()

    def consolidate(self, sequence: Sequence) -> None:
        """ See `sCoda.sequence.relative_sequence.RelativeSequence.consolidate`

        """
        self._get_rel().consolidate(sequence._get_rel())

    def merge(self, sequences: [Sequence]) -> None:
        """ See `sCoda.sequence.absolute_sequence.AbsoluteSequence.merge`

        """
        self._get_abs().merge([seq._get_abs() for seq in sequences])

    def split(self, capacities: [int]) -> [Sequence]:
        """ See `sCoda.sequence.relative_sequence.RelativeSequence.split`

        """
        relative_sequences = self._get_rel().split(capacities)
        sequences = [Sequence(relative_sequence=seq) for seq in relative_sequences]
        return sequences

    def to_midi_track(self) -> MidiTrack:
        """ See `sCoda.sequence.relative_sequence.RelativeSequence.to_midi_track`

        """
        return self._get_rel().to_midi_track()

    def transpose(self, transpose_by: int) -> None:
        """ See `sCoda.sequence.relative_sequence.RelativeSequence.transpose`

        """
        self._get_rel().transpose(transpose_by)

    def quantise(self, divisors: [int]) -> None:
        """ See `sCoda.sequence.absolute_sequence.AbsoluteSequence.quantise`

        """
        self._get_abs().quantise(divisors)

    def quantise_note_lengths(self, upper_bound_multiplier, lower_bound_divisor, dotted_note_iterations=1,
                              standard_length=PPQN) -> None:
        """ See `sCoda.sequence.absolute_sequence.AbsoluteSequence.quantise_note_lengths`

        """
        self._get_abs().quantise_note_lengths(upper_bound_multiplier, lower_bound_divisor,
                                              dotted_note_iterations=dotted_note_iterations,
                                              standard_length=standard_length)
