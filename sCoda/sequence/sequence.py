from __future__ import annotations

from sCoda.elements.message import MessageType
from sCoda.sequence.absolute_sequence import AbsoluteSequence
from sCoda.sequence.relative_sequence import RelativeSequence
from sCoda.settings import PPQN
from sCoda.util.midi_wrapper import MidiTrack
from sCoda.util.util import minmax, simple_regression


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
        self._rel_stale = True

    def add_relative_message(self, msg) -> None:
        """ See `sCoda.sequence.relative_sequence.RelativeSequence.add_message`

        """
        self._get_rel().add_message(msg)
        self._abs_stale = True

    def adjust_wait_messages(self) -> None:
        """ See `sCoda.sequence.relative_sequence.RelativeSequence.adjust_wait_messages`

        """
        self._get_rel().adjust_wait_messages()
        self._abs_stale = True

    def consolidate(self, sequence: Sequence) -> None:
        """ See `sCoda.sequence.relative_sequence.RelativeSequence.consolidate`

        """
        self._get_rel().consolidate(sequence._get_rel())
        self._abs_stale = True

    def difficulty(self) -> float:
        diff_note_values = self._get_abs().diff_note_values()
        diff_note_classes = self._get_abs().diff_note_classes()
        diff_key = self._get_rel().diff_key()
        diff_distances = self._get_rel().diff_distances()
        diff_rhythm = self._get_abs().diff_rhythm()
        diff_pattern = self._get_rel().diff_pattern()

        # print(
        #     f"Note Values: {diff_note_values} Note Classes: {diff_note_classes} Key: {diff_key} "
        #     f"Distances: {diff_distances} Rhythm: {diff_rhythm}")

        difficulties_standard = [(diff_note_values, 10), (diff_note_classes, 6), (diff_key, 5)]
        difficulties_increase = [(diff_distances, 10), (diff_rhythm, 15)]

        difficulty = 0

        standard_weight_sum = sum(weight for _, weight in difficulties_standard)

        for difficulty_standard, weight in difficulties_standard:
            difficulty += difficulty_standard * weight / standard_weight_sum

        increase_percent_points = 0
        for difficulty_increase, percentage_point_bound in difficulties_increase:
            increase_percent_points += minmax(0, percentage_point_bound,
                                              simple_regression(1, percentage_point_bound, 0, 0, difficulty_increase))

        change_percent_points = increase_percent_points

        return difficulty + difficulty * change_percent_points / 100

    def get_timing_of_message_type(self, message_type: MessageType) -> [int]:
        """ See `sCoda.sequence.absolute_sequence.AbsoluteSequence.get_timing_of_message_type`

        """
        return self._get_abs().get_timing_of_message_type(message_type)

    def merge(self, sequences: [Sequence]) -> None:
        """ See `sCoda.sequence.absolute_sequence.AbsoluteSequence.merge`

        """
        self._get_abs().merge([seq._get_abs() for seq in sequences])
        self._rel_stale = True

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
        self._abs_stale = True

    def quantise(self, step_sizes: [int]) -> None:
        """ See `sCoda.sequence.absolute_sequence.AbsoluteSequence.quantise`

        """
        self._get_abs().quantise(step_sizes)
        self._rel_stale = True

    def quantise_note_lengths(self, possible_durations, standard_length=PPQN) -> None:
        """ See `sCoda.sequence.absolute_sequence.AbsoluteSequence.quantise_note_lengths`

        """
        self._get_abs().quantise_note_lengths(possible_durations, standard_length=standard_length)
        self._rel_stale = True
