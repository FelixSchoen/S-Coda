from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from matplotlib import pyplot as plt, pyplot
from matplotlib.patches import Rectangle

from scoda.elements.message import Message
from scoda.enumerations.message_type import MessageType
from scoda.midi.midi_file import MidiFile
from scoda.midi.midi_track import MidiTrack
from scoda.misc.music_theory import Key
from scoda.misc.util import minmax, simple_regression
from scoda.sequences.absolute_sequence import AbsoluteSequence
from scoda.sequences.relative_sequence import RelativeSequence
from scoda.settings.settings import PPQN, NOTE_LOWER_BOUND, NOTE_UPPER_BOUND, VELOCITY_MAX

if TYPE_CHECKING:
    from scoda.elements.bar import Bar


class Sequence:
    """Wrapper for `scoda.sequence.absolute_sequence.AbsoluteSequence` and
    `scoda.sequence.relative_sequence.RelativeSequence`.

    This class serves as a wrapper for the two above-mentioned classes. This abstraction provides an easier
    understanding for the end-user, who does not have to concern themselves with implementational details.
    """

    # General Methods

    def __init__(self, absolute_sequence: AbsoluteSequence = None, relative_sequence: RelativeSequence = None) -> None:
        super().__init__()
        self._abs_stale = True
        self._rel_stale = True

        self._difficulty = None
        self._diff_note_amount = None
        self._diff_note_values = None
        self._diff_note_classes = None
        self._diff_concurrent_notes = None
        self._diff_key = None
        self._diff_accidentals = None
        self._diff_distances = None
        self._diff_rhythm = None
        self._diff_pattern = None

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
        copied_absolute_sequence = None if self.abs is None else copy.copy(self.abs)
        copied_relative_sequence = None if self.rel is None else copy.copy(self.rel)

        cpy = Sequence(copied_absolute_sequence, copied_relative_sequence)

        cpy._difficulty = self._difficulty
        cpy._diff_note_amount = self._diff_note_amount
        cpy._diff_note_values = self._diff_note_values
        cpy._diff_note_classes = self._diff_note_classes
        cpy._diff_concurrent_notes = self._diff_concurrent_notes
        cpy._diff_key = self._diff_key
        cpy._diff_accidentals = self._diff_accidentals
        cpy._diff_distances = self._diff_distances
        cpy._diff_rhythm = self._diff_rhythm
        cpy._diff_pattern = self._diff_pattern

        return cpy

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, Sequence):
            return False

        return self.abs.__eq__(o.abs)

    @property
    def abs(self) -> AbsoluteSequence:
        """Returns a reference to the absolute representation of this sequence.

        Note that if the sequence is modified without interacting via the interface provided by this object,
        the sequence stored in this object might corrupt.

        Returns: The stored AbsoluteSequence

        """
        if self._abs_stale:
            self._abs_stale = False
            self._abs = self._rel.to_absolute_sequence()
        return self._abs

    @property
    def rel(self) -> RelativeSequence:
        """Returns a reference to the relative representation of this sequence.

        Note that if the sequence is modified without interacting via the interface provided by this object,
        the sequence stored in this object might corrupt.

        Returns: The stored RelativeSequence

        """
        if self._rel_stale:
            self._rel_stale = False
            self._rel = self._abs.to_relative_sequence()
        return self._rel

    # Basic Methods

    def add_absolute_message(self, msg) -> None:
        """See `scoda.sequence.absolute_sequence.AbsoluteSequence.add_message`."""
        self.abs.add_message(msg)
        self._rel_stale = True

    def add_relative_message(self, msg) -> None:
        """See `scoda.sequence.relative_sequence.RelativeSequence.add_message`."""
        self.rel.add_message(msg)
        self._abs_stale = True

    def concatenate(self, sequences: list[Sequence]) -> None:
        """See `scoda.sequence.relative_sequence.RelativeSequence.concatenate`."""
        self.rel.concatenate([seq.rel for seq in sequences])
        self._abs_stale = True

    def cutoff(self, maximum_length, reduced_length) -> None:
        """See `scoda.sequence.relative_sequence.AbsoluteSequence.cutoff`."""
        self.abs.cutoff(maximum_length=maximum_length, reduced_length=reduced_length)
        self._rel_stale = True

    def equivalent(self,
                   other,
                   ignore_channel: bool = False,
                   ignore_velocity: bool = False,
                   ignore_time_signatures: bool = True,
                   log_differences: bool = False) -> bool | tuple[bool, str]:
        """See `scoda.sequence.absolute_sequence.AbsoluteSequence.equivalent`."""
        return self.abs.equivalent(other.abs, ignore_channel=ignore_channel, ignore_velocity=ignore_velocity,
                                   ignore_time_signatures=ignore_time_signatures, log_differences=log_differences)

    def merge(self, sequences: list[Sequence]) -> None:
        """See `scoda.sequence.absolute_sequence.AbsoluteSequence.merge`."""
        self.abs.merge([seq.abs for seq in sequences])
        self._rel_stale = True
        self.normalise()

    def normalise(self) -> None:
        """See `scoda.sequence.relative_sequence.RelativeSequence.normalise_relative`."""
        self.rel.normalise_relative()
        self._abs_stale = True

    def pad(self, padding_length) -> None:
        """See `scoda.sequence.relative_sequence.RelativeSequence.pad`."""
        self.rel.pad(padding_length)
        self._abs_stale = True

    def save(self, file_path: str) -> MidiFile:
        """Saves the given sequence as a MIDI file.

        Args:
            file_path: Where to save the sequence to

        Returns: The resulting MidiFile

        """
        return Sequence.sequences_save([self], file_path)

    def set_channel(self, channel: int) -> None:
        """See `scoda.sequence.relative_sequence.RelativeSequence.set_channel`."""
        self.rel.set_channel(channel)
        self._abs_stale = True

    def split(self, capacities: list[int]) -> list[Sequence]:
        """See `scoda.sequence.relative_sequence.RelativeSequence.split`."""
        relative_sequences = self.rel.split(capacities)
        sequences = [Sequence(relative_sequence=seq) for seq in relative_sequences]
        return sequences

    def scale(self, factor, meta_sequence=None, quantise_afterwards=True) -> None:
        """See `scoda.sequence.relative_sequence.RelativeSequence.scale`."""
        self.rel.scale(factor, meta_sequence)
        self._abs_stale = True

        if quantise_afterwards:
            self.quantise_and_normalise()

    def transpose(self, transpose_by: int) -> bool:
        """See `scoda.sequence.relative_sequence.RelativeSequence.transpose`."""
        self._abs_stale = True
        shifted = self.rel.transpose(transpose_by)

        # Possible that notes overlap
        if shifted:
            self.normalise()
            self.quantise_note_lengths()
            self._diff_pattern = None

        if transpose_by % 12 != 0:
            self._diff_key = None
            self._diff_accidentals = None

        return shifted

    def quantise(self, step_sizes: list[int] = None) -> None:
        """See `scoda.sequence.absolute_sequence.AbsoluteSequence.quantise`."""
        self.abs.quantise(step_sizes)
        self._rel_stale = True

    def quantise_note_lengths(self, note_values=None, standard_length=PPQN, do_not_extend=False) -> None:
        """See `scoda.sequence.absolute_sequence.AbsoluteSequence.quantise_note_lengths`."""
        self.abs.quantise_note_lengths(note_values, standard_length=standard_length, do_not_extend=do_not_extend)
        self._rel_stale = True

    def quantise_and_normalise(self, step_sizes: list[int] = None, note_values=None, standard_length=PPQN,
                               do_not_extend=False):
        """Quantises and normalises the sequence."""
        self.quantise(step_sizes)
        self.quantise_note_lengths(note_values, standard_length, do_not_extend)
        self.normalise()

    # Misc. Methods

    def get_message_pairings(self,
                             message_types: list[MessageType] = None,
                             standard_length=PPQN,
                             impute_notes=True) -> dict[list[Message]]:
        """See `scoda.sequence.absolute_sequence.AbsoluteSequence.get_message_pairings`.

        """
        return self.abs.get_message_pairings(message_types=message_types,
                                             standard_length=standard_length,
                                             impute_notes=impute_notes)

    def get_interleaved_message_pairings(self,
                                         message_types: list[MessageType] = None,
                                         standard_length=PPQN,
                                         impute_notes=True) -> list[tuple[int, list[Message]]]:
        """See `scoda.sequence.absolute_sequence.AbsoluteSequence.get_interleaved_message_pairings`.

        """
        return self.abs.get_interleaved_message_pairings(message_types=message_types,
                                                         standard_length=standard_length,
                                                         impute_notes=impute_notes)

    def get_message_times_of_type(self, message_types: [MessageType]) -> list[tuple[int, Message]]:
        """See `scoda.sequence.absolute_sequence.AbsoluteSequence.get_message_timings_of_type`.

        """
        return self.abs.get_message_times_of_type(message_types)

    def get_sequence_channel(self) -> int | None:
        """See `scoda.sequence.absolute_sequence.AbsoluteSequence.get_sequence_channel`.

        """
        return self.abs.get_sequence_channel()

    def get_sequence_duration(self) -> float:
        """See `scoda.sequence.absolute_sequence.AbsoluteSequence.get_sequence_length`.

        """
        return self.abs.get_sequence_duration()

    def get_sequence_duration_relation(self) -> float:
        """See `scoda.sequence.relative_sequence.RelativeSequence.sequence_length_relation`.

        """
        return self.rel.get_sequence_duration_relation()

    def is_channel_consistent(self) -> bool:
        """See `scoda.sequence.absolute_sequence.AbsoluteSequence.is_channel_consistent`.

        """
        return self.abs.is_channel_consistent()

    def is_empty(self) -> bool:
        """See `scoda.sequence.relative_sequence.RelativeSequence.is_empty`.

        """
        return self.rel.is_empty()

    def to_midi_track(self) -> MidiTrack:
        """See `scoda.sequence.relative_sequence.RelativeSequence.to_midi_track`."""
        return self.rel.to_midi_track()

    # Difficulty Methods

    def difficulty(self, key_signature: Key = None) -> float:
        # If difficulty not stale
        if None not in [self._difficulty, self._diff_note_amount, self._diff_note_values, self._diff_note_classes,
                        self._diff_key, self._diff_accidentals, self._diff_distances, self._diff_rhythm,
                        self._diff_pattern, self._diff_concurrent_notes]:
            return self._difficulty

        self.normalise()

        if key_signature is None:
            key_signature = self.rel.get_key_signature_guess()

        difficulty_weights = [
            (self.diff_note_values, 0, 0.45),
            (self.diff_note_amount, 0, 0.5),
            (self.diff_concurrent_notes, 0, 0.475),
            (self.diff_distances, 0, 0.15),
            (self.diff_rhythm, -0.1, 0.2),
            (self.diff_key(key_signature), -0.05, 0.15),
            (self.diff_accidentals(key_signature), -0.05, 0.1),
            (self.diff_note_classes, -0.1, 0.15),
        ]

        difficulty_percentages = [
            (self.diff_pattern, -0.4, 0),
        ]

        overall_difficulty = 0

        for difficulty_weight in difficulty_weights:
            change = simple_regression(0, difficulty_weight[1], 1, difficulty_weight[2], difficulty_weight[0])
            overall_difficulty += change

        percentage_change = 0
        for percentage_weight in difficulty_percentages:
            change = simple_regression(0, percentage_weight[1], 1, percentage_weight[2], percentage_weight[0])
            percentage_change += change
        overall_difficulty *= (1 + percentage_change)

        overall_difficulty = minmax(0, 1, overall_difficulty)

        self._difficulty = overall_difficulty
        return self._difficulty

    @property
    def diff_note_amount(self) -> float:
        if self._diff_note_amount is None:
            self._diff_note_amount = self.rel.diff_note_amount()
        return self._diff_note_amount

    @property
    def diff_note_values(self) -> float:
        if self._diff_note_values is None:
            self._diff_note_values = self.abs.diff_note_values()
        return self._diff_note_values

    @property
    def diff_note_classes(self) -> float:
        if self._diff_note_classes is None:
            self._diff_note_classes = self.rel.diff_note_classes()
        return self._diff_note_classes

    @property
    def diff_concurrent_notes(self) -> float:
        if self._diff_concurrent_notes is None:
            self._diff_concurrent_notes = self.rel.diff_concurrent_notes()
        return self._diff_concurrent_notes

    def diff_key(self, key_signature) -> float:
        if self._diff_key is None:
            self._diff_key = self.rel.diff_key(key=key_signature)
        return self._diff_key

    def diff_accidentals(self, key_signature) -> float:
        if self._diff_accidentals is None:
            self._diff_accidentals = self.rel.diff_accidentals(key=key_signature)
        return self._diff_accidentals

    @property
    def diff_distances(self) -> float:
        if self._diff_distances is None:
            self._diff_distances = self.rel.diff_distances()
        return self._diff_distances

    @property
    def diff_rhythm(self) -> float:
        if self._diff_rhythm is None:
            self._diff_rhythm = self.abs.diff_rhythm()
        return self._diff_rhythm

    @property
    def diff_pattern(self) -> float:
        if self._diff_pattern is None:
            self._diff_pattern = self.rel.diff_pattern()
        return self._diff_pattern

    # Static Functions

    @staticmethod
    def sequences_load(file_path: Path | str = None,
                       midi_file: MidiFile = None,
                       track_indices: list[list[int]] = None,
                       meta_track_indices: list[int] = None,
                       target_meta_track_index: int = 0) -> list[Sequence]:
        """Creates `scoda.Sequence` objects from the provided MIDI file.

        Args:
            midi_file: If provided, this file is used instead of trying to load from a file.
            file_path: The file path of the MIDI file.
            track_indices: A list of lists indicating which tracks of the MIDI file should be merged into which tracks
                of the resulting sequence.
            meta_track_indices: A list of indices of tracks of the MIDI file to consider for meta messages.
            target_meta_track_index: The index of the track of the final sequence that should contain meta messages.

        Returns: A list of `scoda.Sequence` objects.

        """
        if midi_file is None:
            midi_file = MidiFile.open(file_path)

        if track_indices is None:
            track_indices = [[i] for i, _ in enumerate(midi_file.tracks)]
        if meta_track_indices is None:
            meta_track_indices = [i for i, _ in enumerate(midi_file.tracks)]

        # Get sequence from MIDI file
        merged_sequences = midi_file.convert(track_indices, meta_track_indices,
                                             meta_track_index=target_meta_track_index)

        return merged_sequences

    @staticmethod
    def sequences_save(sequences: list[Sequence],
                       file_path: Path | str) -> MidiFile:
        """Saves the given sequence as a MIDI file.

        Args:
            sequences: Sequences to save
            file_path: Where to save the sequence to

        Returns: The resulting MidiFile

        """
        midi_file = MidiFile()
        for sequence in sequences:
            midi_file.tracks.append(sequence.to_midi_track())
        midi_file.save(file_path)

        return midi_file

    @staticmethod
    def sequences_split_bars(sequences_input: list[Sequence],
                             meta_track_index=0,
                             quantise_note_lengths=True) -> list[list[Bar]]:
        """Splits the sequence into a lists of `scoda.Bar`, conforming to the contained time signatures.

        Each list of bars will correspond to one of the given sequence.

        Args:
            sequences_input: The sequence to split.
            meta_track_index: The index of the sequence that contains the time signature changes.
            quantise_note_lengths: Whether the note lengths of the split bar should be quantised after the split.

        Returns: A list of bars.

        """
        from scoda.elements.bar import Bar

        sequences = copy.copy(sequences_input)

        # Split into bars, carry key and time signature
        current_point_in_time = 0
        current_ts_numerator = 4
        current_ts_denominator = 4
        current_key = None

        # Determine signature timings
        meta_track = sequences[meta_track_index]
        time_signature_timings = meta_track.get_message_times_of_type([MessageType.TIME_SIGNATURE])
        key_signature_timings = meta_track.get_message_times_of_type([MessageType.KEY_SIGNATURE])

        tracks_bars = [[] for _ in sequences]

        if len(time_signature_timings) == 0:
            time_signature_timings = [(0,
                                       Message(message_type=MessageType.TIME_SIGNATURE, channel=None,
                                               numerator=current_ts_numerator, denominator=current_ts_denominator))]

        # Keep track of when bars are of equal length
        tracks_synchronised = False

        # Repeat until all tracks of exactly equal length
        while not tracks_synchronised:
            # Obtain new time or key signatures
            time_signature = next((timing for timing in time_signature_timings if timing[0] <= current_point_in_time)
                                  , None)
            key_signature = next((timing for timing in key_signature_timings if timing[0] <= current_point_in_time)
                                 , None)

            # Update time signature
            if time_signature is not None:
                time_signature_timings.pop(0)
                current_ts_numerator = time_signature[1].numerator
                current_ts_denominator = time_signature[1].denominator

            # Update key signature
            if key_signature is not None:
                key_signature_timings.pop(0)
                current_key = key_signature[1].key

            # Calculate length of current bar based on time signature
            length_bar = int(PPQN * (current_ts_numerator / (current_ts_denominator / 4)))
            current_point_in_time += length_bar

            # Assume after this split, tracks are synchronized
            tracks_synchronised = True

            # Split sequence into bars
            for i, sequence in enumerate(sequences):
                split_up = sequence.split([length_bar])

                # Check if we reached the end of the sequence
                if len(split_up) > 1:
                    tracks_synchronised = False
                    sequences[i] = split_up[1]
                # Fill with placeholder empty sequence
                else:
                    if len(split_up) == 0:
                        split_up.append(Sequence())
                    sequences[i] = Sequence()

                # Quantise note lengths, in case splitting into bars affected them
                sequence_to_add = split_up[0]
                if quantise_note_lengths:
                    sequence_to_add.quantise_note_lengths(do_not_extend=True)

                # Append split bar to list of bars
                tracks_bars[i].append(
                    Bar(sequence_to_add, current_ts_numerator, current_ts_denominator,
                        Key(current_key) if current_key is not None else None))

        return tracks_bars

    @staticmethod
    def plot_pianorolls(sequences: [Sequence],
                        title: str = None,
                        x_label: str = None,
                        y_label: str = None,
                        x_scale: list[int] = None,
                        y_scale: list[int] = (NOTE_LOWER_BOUND, NOTE_UPPER_BOUND + 1),
                        show_velocity: bool = True,
                        x_tick_spacing=PPQN,
                        figsize: tuple[int, int] = (10, 6)) -> pyplot:
        """Creates a piano roll from the given sequence.

        Creates a visualisation in form of a piano roll from the given sequence, where each note is visualised using
        a rectangle. The opacity of the rectangles corresponds to the velocity the notes are played with. Options for
        scaling the representation are given, where in the default case height and width of the piano roll are
        selected in such a way that all notes fit exactly.

        Args:
            sequences: The sequence to create a representation for
            title: An optional title to set
            x_label: Label of the x-axis
            y_label: Label of the y-axis
            x_scale: The scale of the x-axis, if not given will be chosen in such a way that all notes fit exactly
            y_scale: The scale of the y-axis, if not given will be chosen in such a way that all notes fit exactly
            show_velocity: Whether to show the velocity by changing the opacity of some notes
            x_tick_spacing: Spacing of the ticks on the x-axis
            figsize: Size of the figure (width, height)

        """
        # Create new figure with specified size
        fig = plt.figure(dpi=300, figsize=figsize)

        # Create subplots for each of the sequence
        gs = fig.add_gridspec(len(sequences), hspace=0.1)
        axs = gs.subplots(sharex=True, sharey=True)

        # Keep track of length and range of sequence
        x_scale_max = 0
        y_scale_min = NOTE_UPPER_BOUND
        y_scale_max = NOTE_LOWER_BOUND

        # Workaround for single sequence
        if len(sequences) == 1:
            axs = [axs]

        # Draw notes
        for i, sequence in enumerate(sequences):
            channel_pairings = sequence.abs.get_message_pairings()

            for message_pairings in channel_pairings.values():
                for note in message_pairings:
                    start_time = note[0].time
                    duration = note[1].time - start_time
                    pitch = note[0].note

                    # Keep track of scales
                    if pitch < y_scale_min:
                        y_scale_min = pitch
                    if pitch > y_scale_max:
                        y_scale_max = pitch

                    # Calculate opacity based on velocity
                    opacity = simple_regression(1, 1, 0, 0.5, note[0].velocity / VELOCITY_MAX)

                    # Draw rectangle
                    axs[i].add_patch(
                        Rectangle((start_time, pitch), duration, 1,
                                  facecolor=(0, 0, 0, 1 if not show_velocity else opacity)))

            # Get length of sequence (if wait messages occur after notes)
            length = 0
            for msg in sequence.rel._messages:
                if msg.message_type == MessageType.WAIT:
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

        return plt

    # Private Functions

    @staticmethod
    def _fill_dictionary_entry(entry,
                               msg_type=None,
                               time=None,
                               note=None,
                               velocity=None,
                               control=None,
                               program=None,
                               numerator=None,
                               denominator=None,
                               key=None,
                               rel_note_dist=None,
                               rel_note_pair_dist=None,
                               rel_note_pair_oct=None):
        entry["msg_type"] = msg_type
        entry["time"] = time
        entry["note"] = note
        entry["velocity"] = velocity
        entry["control"] = control
        entry["program"] = program
        entry["numerator"] = numerator
        entry["denominator"] = denominator
        entry["key"] = key
        entry["rel_distance"] = rel_note_dist
        entry["rel_note_pair_dist"] = rel_note_pair_dist
        entry["rel_note_pair_oct"] = rel_note_pair_oct
