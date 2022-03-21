from __future__ import annotations

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle

from sCoda.elements.message import MessageType, Message
from sCoda.sequence.absolute_sequence import AbsoluteSequence
from sCoda.sequence.relative_sequence import RelativeSequence
from sCoda.settings import PPQN, NOTE_LOWER_BOUND, NOTE_UPPER_BOUND, MAX_VELOCITY
from sCoda.util.midi_wrapper import MidiTrack
from sCoda.util.music_theory import Key
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

    def difficulty(self, key_signature: Key = None) -> float:
        diff_note_values = self._get_abs().diff_note_values()
        diff_note_classes = self._get_abs().diff_note_classes()
        diff_key = self._get_rel().diff_key(key=key_signature)
        diff_distances = self._get_rel().diff_distances()
        diff_rhythm = self._get_abs().diff_rhythm()
        diff_pattern = self._get_rel().diff_pattern()

        difficulties_standard = [(diff_note_values, 10), (diff_note_classes, 6), (diff_key, 5)]
        difficulties_increase = [(diff_distances, 10), (diff_rhythm, 15)]
        difficulties_decrease = [(diff_pattern, 50)]

        difficulty = 0

        standard_weight_sum = sum(weight for _, weight in difficulties_standard)

        # Calculate base difficulty
        for difficulty_standard, weight in difficulties_standard:
            difficulty += difficulty_standard * weight / standard_weight_sum

        # Calculate increase of difficulty
        increase_percent_points = 0
        for difficulty_increase, percentage_point_bound in difficulties_increase:
            increase_percent_points += minmax(0, percentage_point_bound,
                                              simple_regression(1, percentage_point_bound, 0, 0, difficulty_increase))
        change_percent_points = increase_percent_points

        # Calculate decrease of difficulty
        decrease_percent_points = 0
        for difficulty_decrease, percentage_point_bound in difficulties_decrease:
            decrease_percent_points += minmax(0, percentage_point_bound,
                                              simple_regression(0, percentage_point_bound, 1, 0, difficulty_decrease))
        change_percent_points -= decrease_percent_points

        overall_difficulty = difficulty + difficulty * change_percent_points / 100

        # print(
        #     f"Overall: {overall_difficulty} Note Values: {diff_note_values} Note Classes: {diff_note_classes} Key: {diff_key} "
        #     f"Distances: {diff_distances} Rhythm: {diff_rhythm} Pattern: {diff_pattern}")

        return overall_difficulty

    def get_timing_of_message_type(self, message_type: MessageType) -> [(int, Message)]:
        """ See `sCoda.sequence.absolute_sequence.AbsoluteSequence.get_timing_of_message_type`

        """
        return self._get_abs().get_timing_of_message_type(message_type)

    def merge(self, sequences: [Sequence]) -> None:
        """ See `sCoda.sequence.absolute_sequence.AbsoluteSequence.merge`

        """
        self._get_abs().merge([seq._get_abs() for seq in sequences])
        self._rel_stale = True

    def pianoroll(self):
        self._get_abs().pianoroll()

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

    @staticmethod
    def pianorolls(sequences: [Sequence],
                   title: str = None,
                   x_label: str = None,
                   y_label: str = None,
                   x_scale: [int] = None,
                   y_scale: [int] = (NOTE_LOWER_BOUND, NOTE_UPPER_BOUND),
                   show_velocity: bool = True,
                   x_tick_spacing=PPQN):
        # Create new figure
        fig = plt.figure(dpi=300)

        # Create subplots for each of the sequences
        gs = fig.add_gridspec(len(sequences), hspace=0.1)
        axs = gs.subplots(sharex=True, sharey=True)

        # Keep track of length and range of sequence
        x_scale_max = 0
        y_scale_min = NOTE_UPPER_BOUND
        y_scale_max = NOTE_LOWER_BOUND

        # Workaround for single sequences
        if len(sequences) == 1:
            axs = [axs]

        # Draw notes
        for i, sequence in enumerate(sequences):
            note_array = sequence._get_abs()._get_absolute_note_array()

            for note in note_array:
                start_time = note[0].time
                duration = note[1].time - start_time
                pitch = note[0].note

                # Keep track of scales
                x_scale_max = max(x_scale_max, start_time + duration)
                if pitch < y_scale_min:
                    y_scale_min = pitch
                if pitch > y_scale_max:
                    y_scale_max = pitch

                # Calculate opacity based on velocity
                opacity = simple_regression(1, 1, 0, 0.5, note[0].velocity / MAX_VELOCITY)

                # Draw rectangle
                axs[i].add_patch(
                    Rectangle((start_time, pitch), duration, 1,
                              facecolor=(0, 0, 0, 1 if not show_velocity else opacity)))

        # Define scale of plot
        if x_scale is None:
            x_scale = [0, x_scale_max]
        if y_scale is None:
            y_scale = [y_scale_min, y_scale_max + 1]
        else:
            y_scale = [y_scale[0], y_scale[1]]

        for ax in axs:
            ax.label_outer()

            # X Ticks
            ax.set_xticks(ticks=np.arange(0, ((x_scale[1] / x_tick_spacing) + 1) * x_tick_spacing, x_tick_spacing))

            # Y Ticks
            ax.set_yticks(ticks=np.arange(24, 24 + (8 + 1) * 12, 12),
                          labels=["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"])
            ax.set_yticks(ticks=np.arange(NOTE_LOWER_BOUND, NOTE_UPPER_BOUND + 1, 1), minor=True)

            # Activate grid
            ax.grid(visible=True)

        # Title plot
        plt.suptitle(title, fontsize=20)

        # Label axis
        fig.supxlabel(x_label)
        fig.supylabel(y_label)

        # Define scale
        plt.xlim(x_scale)
        plt.ylim(y_scale)

        plt.show()
