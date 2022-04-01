from __future__ import annotations

import copy

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle
from pandas import DataFrame

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

    def __copy__(self) -> Sequence:
        copied_absolute_sequence = None if self._get_abs() is None else self._get_abs().__copy__()
        copied_relative_sequence = None if self._get_rel() is None else self._get_rel().__copy__()

        return Sequence(copied_absolute_sequence, copied_relative_sequence)

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
        self.adjust_wait_messages()

        diff_note_amount = self._get_rel().diff_note_amount()
        diff_note_values = self._get_abs().diff_note_values()
        diff_note_classes = self._get_rel().diff_note_classes()
        diff_key = self._get_rel().diff_key(key=key_signature)
        diff_distances = self._get_rel().diff_distances()
        diff_rhythm = self._get_abs().diff_rhythm()
        diff_pattern = self._get_rel().diff_pattern()

        difficulties_standard = [(diff_note_values, 10), (diff_note_amount, 8), (diff_note_classes, 6), (diff_key, 5)]
        difficulties_increase = [(diff_distances, 10), (diff_rhythm, 25)]
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
        #     f"Overall: {overall_difficulty} Note Values: {diff_note_values} Note Amount: {diff_note_amount} Note "
        #     f"Classes: {diff_note_classes} Key: {diff_key} Distances: {diff_distances} Rhythm: {diff_rhythm} "
        #     f"Pattern: {diff_pattern}")

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

    def pad_sequence(self, padding_length):
        """ See `sCoda.sequence.relative_sequence.RelativeSequence.pad_sequence`

        """
        self._get_rel().pad_sequence(padding_length)
        self._abs_stale = True

    def sequence_length(self) -> float:
        """ See `sCoda.sequence.relative_sequence.RelativeSequence.sequence_length`

        """
        return self._get_rel().sequence_length_relation()

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

    def to_absolute_dataframe(self) -> DataFrame:
        """ Creates a `DataFrame` from the messages in this sequence.

        Returns: A `DataFrame` filled with all the messages in this sequence in their textual or numeric representation

        """
        return Sequence.to_dataframe(self._get_abs().messages)

    def to_relative_dataframe(self, adjust_wait_messages=True) -> DataFrame:
        """ Creates a `DataFrame` from the messages in this sequence.

        Args:
            adjust_wait_messages: Whether to adjust the wait messages in this sequence or not

        Returns: A `DataFrame` filled with all the messages in this sequence in their textual or numeric representation

        """
        relative_sequence = copy.copy(self._get_rel())

        if adjust_wait_messages:
            relative_sequence.adjust_wait_messages()

        return Sequence.to_dataframe(relative_sequence.messages)

    def transpose(self, transpose_by: int) -> bool:
        """ See `sCoda.sequence.relative_sequence.RelativeSequence.transpose`

        """
        self._abs_stale = True
        shifted = self._get_rel().transpose(transpose_by)

        if shifted:
            self.quantise_note_lengths()

        return shifted

    def quantise(self, step_sizes: [int]) -> None:
        """ See `sCoda.sequence.absolute_sequence.AbsoluteSequence.quantise`

        """
        self._get_abs().quantise(step_sizes)
        self._rel_stale = True

    def quantise_note_lengths(self, possible_durations=None, standard_length=PPQN) -> None:
        """ See `sCoda.sequence.absolute_sequence.AbsoluteSequence.quantise_note_lengths`

        """
        self._get_abs().quantise_note_lengths(possible_durations, standard_length=standard_length)
        self._rel_stale = True

    @staticmethod
    def to_dataframe(messages) -> DataFrame:
        data = []

        for msg in messages:
            data.append(
                {"message_type": msg.message_type.value, "time": msg.time, "note": msg.note,
                 "velocity": msg.velocity,
                 "control": msg.control, "numerator": msg.numerator, "denominator": msg.denominator,
                 "key": None if msg.key is None else msg.key.value})

        return pd.DataFrame(data)

    @staticmethod
    def pianorolls(sequences: [Sequence],
                   title: str = None,
                   x_label: str = None,
                   y_label: str = None,
                   x_scale: [int] = None,
                   y_scale: [int] = (NOTE_LOWER_BOUND, NOTE_UPPER_BOUND),
                   show_velocity: bool = True,
                   x_tick_spacing=PPQN) -> None:
        """ Creates a piano roll from the given sequences.

        Creates a visualisation in form of a piano roll from the given sequences, where each note is visualised using
        a rectangle. The opacity of the rectangles corresponds to the velocity the notes are played with. Options for
        scaling the representation are given, where in the default case height and width of the piano roll are
        selected in such a way that all notes fit exactly.

        Args:
            sequences: The sequences to create a representation for
            title: An optional title to set
            x_label: Label of the x-axis
            y_label: Label of the y-axis
            x_scale: The scale of the x-axis, if not given will be chosen in such a way that all notes fit exactly
            y_scale: The scale of the y-axis, if not given will be chosen in such a way that all notes fit exactly
            show_velocity: Whether to show the velocity by changing the opacity of some notes
            x_tick_spacing: Spacing of the ticks on the x-axis

        """
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

            # Get length of sequence (if wait messages occur after notes)
            length = 0
            for msg in sequence._get_rel().messages:
                if msg.message_type == MessageType.wait:
                    length += msg.time

            x_scale_max = max(x_scale_max, length)

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
