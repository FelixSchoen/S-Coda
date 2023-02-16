from __future__ import annotations

import copy
import enum

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt, pyplot
from matplotlib.patches import Rectangle
from pandas import DataFrame

import s_coda
from s_coda.elements.message import MessageType, Message
from s_coda.sequence.absolute_sequence import AbsoluteSequence
from s_coda.sequence.relative_sequence import RelativeSequence
from s_coda.settings import PPQN, NOTE_LOWER_BOUND, NOTE_UPPER_BOUND, MAX_VELOCITY
from s_coda.util.midi_wrapper import MidiTrack, MidiFile
from s_coda.util.music_theory import Key, Note, CircleOfFifths
from s_coda.util.util import minmax, simple_regression


class NoteRepresentationType(enum.Enum):
    absolute_values = 0
    relative_distances = 1
    circle_of_fifths = 2
    scale = 3


class TemporalRepresentationType(enum.Enum):
    relative_ticks = 0
    notelike_representation = 1


class Sequence:
    """ Wrapper for `s_coda.sequence.absolute_sequence.AbsoluteSequence` and
    `s_coda.sequence.relative_sequence.RelativeSequence`.

    This class serves as a wrapper for the two above-mentioned classes. This abstraction provides an easier
    understanding for the end-user, who does not have to concern themselves with implementational details.
    """

    # === General ===

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
        copied_absolute_sequence = None if self.abs is None else self.abs.__copy__()
        copied_relative_sequence = None if self.rel is None else self.rel.__copy__()

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

    @property
    def abs(self) -> AbsoluteSequence:
        """ Returns a reference to the absolute representation of this sequence.

        Note that if the sequence is modified without interacting via the interface provided by this object, the sequence
        stored in this object might corrupt.

        Returns: The stored AbsoluteSequence

        """
        if self._abs_stale:
            self._abs_stale = False
            self._abs = self._rel.to_absolute_sequence()
        return self._abs

    @property
    def rel(self) -> RelativeSequence:
        """ Returns a reference to the relative representation of this sequence.

        Note that if the sequence is modified without interacting via the interface provided by this object, the sequence
        stored in this object might corrupt.

        Returns: The stored RelativeSequence

        """
        if self._rel_stale:
            self._rel_stale = False
            self._rel = self._abs.to_relative_sequence()
        return self._rel

    # === Methods ===

    def add_absolute_message(self, msg) -> None:
        """ See `s_coda.sequence.absolute_sequence.AbsoluteSequence.add_message`

        """
        self.abs.add_message(msg)
        self._rel_stale = True

    def add_relative_message(self, msg) -> None:
        """ See `s_coda.sequence.relative_sequence.RelativeSequence.add_message`

        """
        self.rel.add_message(msg)
        self._abs_stale = True

    def adjust_messages(self) -> None:
        """ See `s_coda.sequence.relative_sequence.RelativeSequence.adjust_messages`

        """
        self.rel.adjust_messages()
        self._abs_stale = True

    def concatenate(self, sequences: [Sequence]) -> None:
        """ See `s_coda.sequence.relative_sequence.RelativeSequence.concatenate`

        """
        self.rel.concatenate([seq.rel for seq in sequences])
        self._abs_stale = True

    def cutoff(self, maximum_length, reduced_length) -> None:
        """ See `s_coda.sequence.relative_sequence.AbsoluteSequence.cutoff`

        """
        self.abs.cutoff(maximum_length=maximum_length, reduced_length=reduced_length)
        self._rel_stale = True

    def difficulty(self, key_signature: Key = None) -> float:
        # If difficulty not stale
        if None not in [self._difficulty, self._diff_note_amount, self._diff_note_values, self._diff_note_classes,
                        self._diff_key, self._diff_accidentals, self._diff_distances, self._diff_rhythm,
                        self._diff_pattern, self._diff_concurrent_notes]:
            return self._difficulty

        self.adjust_messages()

        if key_signature is None:
            key_signature = self.rel.guess_key_signature()

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

    def get_message_timing(self, message_type: MessageType) -> [(int, Message)]:
        """ See `s_coda.sequence.absolute_sequence.AbsoluteSequence.get_message_timing`

        """
        return self.abs.get_message_timing(message_type)

    def is_empty(self) -> bool:
        """ See `s_coda.sequence.relative_sequence.RelativeSequence.is_empty`

        """
        return self.rel.is_empty()

    def merge(self, sequences: [Sequence]) -> None:
        """ See `s_coda.sequence.absolute_sequence.AbsoluteSequence.merge`

        """
        self.abs.merge([seq.abs for seq in sequences])
        self._rel_stale = True

    def pad_sequence(self, padding_length):
        """ See `s_coda.sequence.relative_sequence.RelativeSequence.pad_sequence`

        """
        self.rel.pad_sequence(padding_length)
        self._abs_stale = True

    def save(self, file_path: str) -> MidiFile:
        """ Saves the given sequence as a MIDI file.

        Args:
            file_path: Where to save the sequence to

        Returns: The resulting MidiFile

        """
        return Sequence.save_sequences([self], file_path)

    def sequence_length(self) -> float:
        """ See `s_coda.sequence.absolute_sequence.AbsoluteSequence.sequence_length`

        """
        return self.abs.sequence_length()

    def sequence_length_relation(self) -> float:
        """ See `s_coda.sequence.relative_sequence.RelativeSequence.sequence_length_relation`

        """
        return self.rel.sequence_length_relation()

    def split(self, capacities: [int]) -> [Sequence]:
        """ See `s_coda.sequence.relative_sequence.RelativeSequence.split`

        """
        relative_sequences = self.rel.split(capacities)
        sequences = [Sequence(relative_sequence=seq) for seq in relative_sequences]
        return sequences

    def scale(self, factor, meta_sequence=None) -> None:
        """ See `s_coda.sequence.relative_sequence.RelativeSequence.scale`

        """
        self.rel.scale(factor, meta_sequence)
        self._abs_stale = True

    def to_midi_track(self) -> MidiTrack:
        """ See `s_coda.sequence.relative_sequence.RelativeSequence.to_midi_track`

        """
        return self.rel.to_midi_track()

    def to_external_representation(self, note_representation_type: NoteRepresentationType,
                                   temporal_representation_type: TemporalRepresentationType,
                                   adjust_wait_messages=True) -> DataFrame:
        data = []

        absolute_sequence = copy.copy(self.abs)
        relative_sequence = copy.copy(self.rel)
        if adjust_wait_messages:
            relative_sequence.adjust_messages()

        if temporal_representation_type == TemporalRepresentationType.relative_ticks:
            base_note = 69  # A4, 440 Hz

            for msg in relative_sequence.messages:
                entry = dict()

                if note_representation_type == NoteRepresentationType.absolute_values:
                    Sequence._fill_dictionary_entry(entry,
                                                    message_type=msg.message_type.value,
                                                    time=msg.time,
                                                    note=msg.note,
                                                    velocity=msg.velocity,
                                                    control=msg.control,
                                                    program=msg.program,
                                                    numerator=msg.numerator,
                                                    denominator=msg.denominator,
                                                    key=None if msg.key is None else msg.key.value)
                elif note_representation_type == NoteRepresentationType.relative_distances:
                    Sequence._fill_dictionary_entry(entry,
                                                    message_type=msg.message_type.value,
                                                    time=msg.time,
                                                    note=msg.note,
                                                    velocity=msg.velocity,
                                                    control=msg.control,
                                                    program=msg.program,
                                                    numerator=msg.numerator,
                                                    denominator=msg.denominator,
                                                    key=None if msg.key is None else msg.key.value,
                                                    rel_distance=None if msg.note is None else (
                                                                                                       msg.note - base_note) % 12,
                                                    rel_octave=None if msg.note is None else (
                                                                                                     msg.note - base_note) // 12)
                elif note_representation_type == NoteRepresentationType.circle_of_fifths:
                    if msg.note is not None:
                        distance = Sequence._circle_of_fifths(base_note, msg.note)

                        Sequence._fill_dictionary_entry(entry,
                                                        message_type=msg.message_type.value,
                                                        time=msg.time,
                                                        note=msg.note,
                                                        velocity=msg.velocity,
                                                        control=msg.control,
                                                        program=msg.program,
                                                        numerator=msg.numerator,
                                                        denominator=msg.denominator,
                                                        key=None if msg.key is None else msg.key.value,
                                                        rel_distance=None if msg.note is None else distance,
                                                        rel_octave=None if msg.note is None else (
                                                                                                         msg.note - base_note) // 12)

                if msg.note is not None:
                    base_note = msg.note
                data.append(entry)
        elif temporal_representation_type == TemporalRepresentationType.notelike_representation:
            base_note = 69  # A4, 440 Hz
            note_array = absolute_sequence._get_absolute_note_array()
            current_point_in_time = 0

            for note_pairing in note_array:
                entry = dict()

                if current_point_in_time != note_pairing[0].time:
                    Sequence._fill_dictionary_entry(entry,
                                                    message_type=MessageType.wait,
                                                    time=note_pairing[0].time - current_point_in_time)
                    current_point_in_time = note_pairing[0].time
                    data.append(entry)
                    entry = dict()

                if note_representation_type == NoteRepresentationType.absolute_values:
                    Sequence._fill_dictionary_entry(entry,
                                                    message_type=MessageType.note_on,
                                                    time=note_pairing[1].time - note_pairing[0].time,
                                                    note=note_pairing[0].note,
                                                    velocity=note_pairing[0].velocity)
                elif note_representation_type == NoteRepresentationType.relative_distances:
                    Sequence._fill_dictionary_entry(entry,
                                                    message_type=MessageType.note_on,
                                                    time=note_pairing[1].time - note_pairing[0].time,
                                                    note=note_pairing[0].note,
                                                    velocity=note_pairing[0].velocity,
                                                    rel_distance=(note_pairing[0].note - base_note) % 12,
                                                    rel_octave=(note_pairing[0].note - base_note) // 12)
                elif note_representation_type == NoteRepresentationType.circle_of_fifths:
                    distance = Sequence._circle_of_fifths(base_note, note_pairing[0].note)

                    Sequence._fill_dictionary_entry(entry,
                                                    message_type=MessageType.note_on,
                                                    time=note_pairing[1].time - note_pairing[0].time,
                                                    note=note_pairing[0].note,
                                                    velocity=note_pairing[0].velocity,
                                                    rel_distance=distance,
                                                    rel_octave=(note_pairing[0].note - base_note) // 12)

                base_note = note_pairing[0].note
                data.append(entry)

        return pd.DataFrame(data)

    def to_absolute_dataframe(self) -> DataFrame:
        """ Creates a `DataFrame` from the messages in this sequence.

        Returns: A `DataFrame` filled with all the messages in this sequence in their textual or numeric representation

        """
        return Sequence.to_dataframe(self.abs.messages)

    def to_relative_dataframe(self, adjust_wait_messages=True) -> DataFrame:
        """ Creates a `DataFrame` from the messages in this sequence.

        Args:
            adjust_wait_messages: Whether to adjust the wait messages in this sequence or not

        Returns: A `DataFrame` filled with all the messages in this sequence in their textual or numeric representation

        """
        relative_sequence = copy.copy(self.rel)

        if adjust_wait_messages:
            relative_sequence.adjust_messages()

        return Sequence.to_dataframe(relative_sequence.messages)

    def transpose(self, transpose_by: int) -> bool:
        """ See `s_coda.sequence.relative_sequence.RelativeSequence.transpose`

        """
        self._abs_stale = True
        shifted = self.rel.transpose(transpose_by)

        # Possible that notes overlap
        if shifted:
            self._diff_pattern = None
            self.quantise_note_lengths()

        if transpose_by % 12 != 0:
            self._diff_key = None
            self._diff_accidentals = None

        return shifted

    def quantise(self, step_sizes: [int] = None) -> None:
        """ See `s_coda.sequence.absolute_sequence.AbsoluteSequence.quantise`

        """
        self.abs.quantise(step_sizes)
        self._rel_stale = True

    def quantise_note_lengths(self, possible_durations=None, standard_length=PPQN, do_not_extend=False) -> None:
        """ See `s_coda.sequence.absolute_sequence.AbsoluteSequence.quantise_note_lengths`

        """
        self.abs.quantise_note_lengths(possible_durations, standard_length=standard_length, do_not_extend=do_not_extend)
        self._rel_stale = True

    # === Static Methods ===

    @staticmethod
    def save_sequences(sequences: [Sequence], file_path: str):
        """ Saves the given sequences as a MIDI file.

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
    def from_midi_file(file_path: str, track_indices: [[int]] = None,
                       meta_track_indices: [int] = None, meta_track_index: int = 0) -> [s_coda.Sequence]:
        """ Creates `s_coda.Sequence` objects from the provided MIDI file.

        Args:
            file_path: The file path of the MIDI file
            track_indices: A list of lists indicating which tracks of the MIDI file should be merged into which tracks
                of the resulting sequence.
            meta_track_indices: A list of indices of tracks of the MIDI file to consider for meta messages
            meta_track_index: The index of the track of the final sequence that should contain meta messages

        Returns: An array of `s_coda.Sequence` objects

        """
        # Open file
        midi_file = MidiFile.open_midi_file(file_path)

        if track_indices is None:
            track_indices = [[i] for i, _ in enumerate(midi_file.tracks)]
        if meta_track_indices is None:
            meta_track_indices = [i for i, _ in enumerate(midi_file.tracks)]

        # Get sequences from MIDI file
        merged_sequences = midi_file.to_sequences(track_indices, meta_track_indices,
                                                  meta_track_index=meta_track_index)

        return merged_sequences

    @staticmethod
    def split_into_bars(sequences_input: [Sequence], meta_track_index=0, quantise_note_lengths=True) -> [[s_coda.Bar]]:
        """ Splits the sequences into a lists of `s_coda.Bar`, conforming to the contained time signatures.

        Each list of bars will correspond to one of the given sequences.

        Args:
            sequences_input: The sequences to split
            meta_track_index: The index of the sequence that contains the time signature changes
            quantise_note_lengths: Whether the note lengths of the split bar should be quantised again

        Returns: A list of bars

        """

        from s_coda import Bar

        sequences = copy.copy(sequences_input)

        # Split into bars, carry key and time signature
        current_point_in_time = 0
        current_ts_numerator = 4
        current_ts_denominator = 4
        current_key = None

        # Determine signature timings
        meta_track = sequences[meta_track_index]
        time_signature_timings = meta_track.get_message_timing(MessageType.time_signature)
        key_signature_timings = meta_track.get_message_timing(MessageType.key_signature)

        tracks_bars = [[] for _ in sequences]

        if len(time_signature_timings) == 0:
            time_signature_timings = [(0,
                                       Message(message_type=MessageType.time_signature, numerator=current_ts_numerator,
                                               denominator=current_ts_denominator))]

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
            length_bar = PPQN * (current_ts_numerator / (current_ts_denominator / 4))
            current_point_in_time += length_bar

            # Assume after this split, tracks are synchronized
            tracks_synchronised = True

            # Split sequences into bars
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

                # Quantise note lengths again, in case splitting into bars affected them
                sequence_to_add = split_up[0]
                if quantise_note_lengths:
                    sequence_to_add.quantise_note_lengths(do_not_extend=True)

                # Append split bar to list of bars
                tracks_bars[i].append(
                    Bar(sequence_to_add, current_ts_numerator, current_ts_denominator,
                        Key(current_key) if current_key is not None else None))

        return tracks_bars

    @staticmethod
    def to_dataframe(messages) -> DataFrame:
        data = []

        for msg in messages:
            data.append(
                {"message_type": msg.message_type.value, "time": msg.time, "note": msg.note,
                 "velocity": msg.velocity, "control": msg.control, "program": msg.program,
                 "numerator": msg.numerator, "denominator": msg.denominator,
                 "key": None if msg.key is None else msg.key.value})

        return pd.DataFrame(data)

    @staticmethod
    def pianorolls(sequences: [Sequence],
                   title: str = None,
                   x_label: str = None,
                   y_label: str = None,
                   x_scale: [int] = None,
                   y_scale: [int] = (NOTE_LOWER_BOUND, NOTE_UPPER_BOUND + 1),
                   show_velocity: bool = True,
                   x_tick_spacing=PPQN) -> pyplot:
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
            note_array = sequence.abs._get_absolute_note_array()

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
            for msg in sequence.rel.messages:
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

        return plt

    # === Helper Methods ===

    @staticmethod
    def _fill_dictionary_entry(entry, message_type=None, time=None, note=None, velocity=None, control=None,
                               program=None, numerator=None, denominator=None, key=None, rel_distance=None,
                               rel_octave=None):
        entry["type"] = message_type
        entry["time"] = time
        entry["note"] = note
        entry["velocity"] = velocity
        entry["control"] = control
        entry["program"] = program
        entry["numerator"] = numerator
        entry["denominator"] = denominator
        entry["key"] = key
        entry["rel_distance"] = rel_distance
        entry["rel_octave"] = rel_octave

    @staticmethod
    def _circle_of_fifths(base_note, note):
        current_note = Note(note % 12)
        previous_note = Note(base_note % 12)

        cof_current_index = CircleOfFifths.index(current_note)
        cof_previous_index = CircleOfFifths.index(previous_note)

        distance_left = cof_previous_index - cof_current_index
        distance_right = np.sign(distance_left) * -1 * 12 + distance_left

        # Get smaller distance
        distance = distance_left if abs(distance_left) < abs(distance_right) else distance_right
        if abs(distance_left) == abs(distance_right):
            distance = distance_left if distance_left > distance_right else distance_right

        return distance
