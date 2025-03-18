from __future__ import annotations

import copy
import math
from typing import TYPE_CHECKING

from scoda.elements.message import Message
from scoda.enumerations.message_type import MessageType
from scoda.exceptions.sequence_exception import SequenceException
from scoda.midi.midi_message import MidiMessage
from scoda.midi.midi_track import MidiTrack
from scoda.misc.music_theory import Note, Key, MusicMapping
from scoda.misc.scoda_logging import get_logger
from scoda.sequences.abstract_sequence import AbstractSequence
from scoda.settings.settings import NOTE_LOWER_BOUND, NOTE_UPPER_BOUND, PPQN

if TYPE_CHECKING:
    from scoda.sequences.absolute_sequence import AbsoluteSequence


class RelativeSequence(AbstractSequence):
    """Class representing a sequence with relative message timings.
    """

    LOGGER = get_logger(__name__)

    # General Methods

    def __init__(self, messages: list = None) -> None:
        super().__init__(messages=messages)

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, RelativeSequence):
            return False

        return self.to_absolute_sequence() == o.to_absolute_sequence()

    def to_absolute_sequence(self) -> AbsoluteSequence:
        """Converts this `RelativeSequence` to an `AbsoluteSequence`.

        Returns: The absolute representation of this sequence.

        """
        from scoda.sequences.absolute_sequence import AbsoluteSequence
        absolute_sequence = AbsoluteSequence()
        current_point_in_time = 0
        default_channel = None
        cap_message_exists = True

        for msg in self._messages:
            if default_channel is None and msg.channel is not None:
                default_channel = msg.channel

            if msg.message_type == MessageType.WAIT:
                current_point_in_time += msg.time
                cap_message_exists = False
            else:
                message_to_add = msg.copy()
                message_to_add.time = current_point_in_time
                absolute_sequence._add_message_unsorted(message_to_add)
                cap_message_exists = True

        absolute_sequence.normalise_absolute()

        if not cap_message_exists:
            absolute_sequence.add_message(
                Message(message_type=MessageType.INTERNAL, channel=default_channel, time=int(current_point_in_time)))

        return absolute_sequence

    # Basic Methods

    def add_message(self, msg: Message, index=None) -> None:
        """Adds the given message to the sequence at the (optionally) given index."""
        if index is None:
            self._messages.append(msg)
        else:
            self._messages.insert(index, msg)

    def concatenate(self, sequences: list[RelativeSequence]) -> None:
        """Concatenates the sequence with the given sequences, resulting in this sequence containing the combined
        messages of itself and the given sequences.

        Args:
            sequences: A sequence which should be appended to this sequence.

        """
        for seq in sequences:
            self._messages.extend([msg for msg in seq._messages])

    def normalise_relative(self) -> None:
        """Removes invalid open and close messages. Consolidates wait messages. Removes double time signatures and key signatures.

        """
        open_messages = dict()
        messages_normalized = []
        wait_buffer = 0

        current_ts_numerator = None
        current_ts_denominator = None
        current_key = None
        default_channel = None

        for msg in self._messages:
            # Infer default channel
            if default_channel is None and msg.channel is not None:
                default_channel = msg.channel

            open_messages.setdefault(msg.channel, dict())

            if msg.message_type == MessageType.WAIT:
                wait_buffer += msg.time
            else:
                if msg.message_type == MessageType.NOTE_ON:
                    note_list = open_messages[msg.channel].get(msg.note, [])
                    note_list.append(msg)
                    open_messages[msg.channel][msg.note] = note_list

                    # Skip message if note is already open
                    if len(note_list) != 1:
                        continue
                elif msg.message_type == MessageType.NOTE_OFF:
                    note_list = open_messages[msg.channel].get(msg.note, [])
                    if len(note_list) > 0:
                        note_list.pop(-1)
                    open_messages[msg.channel][msg.note] = note_list

                    # Skip message if note not yet closed
                    if len(note_list) != 0:
                        continue
                # Remove double time signatures
                elif msg.message_type == MessageType.TIME_SIGNATURE:
                    if msg.numerator != current_ts_numerator or msg.denominator != current_ts_denominator:
                        current_ts_numerator = msg.numerator
                        current_ts_denominator = msg.denominator
                    else:
                        continue
                elif msg.message_type == MessageType.KEY_SIGNATURE:
                    if msg.key != current_key:
                        current_key = msg.key
                    else:
                        continue

                # Insert consolidated wait message
                if wait_buffer > 0:
                    messages_normalized.append(
                        Message(message_type=MessageType.WAIT, channel=msg.channel, time=wait_buffer))
                    wait_buffer = 0

                messages_normalized.append(msg)

        # Repeat procedure for wait messages that occur at the end of the sequence
        if wait_buffer > 0:
            messages_normalized.append(
                Message(message_type=MessageType.WAIT, channel=default_channel, time=wait_buffer))

        # Remove unclosed notes
        for channel in open_messages.keys():
            for key in open_messages.keys():
                note_list = open_messages[channel].get(key, [])
                for msg in note_list:
                    if msg in messages_normalized:
                        messages_normalized.remove(msg)

        self._messages = messages_normalized

    def pad(self, padding_length) -> None:
        """Pads the sequence to a minimum fixed length.

        Args:
            padding_length: The minimum length this sequence should have after this operation.

        """
        current_length = 0
        default_channel = None

        for msg in self._messages:
            if default_channel is None and msg.channel is not None:
                default_channel = msg.channel

            if msg.message_type == MessageType.WAIT:
                current_length += msg.time

                if current_length >= padding_length:
                    break

        if current_length < padding_length:
            self._messages.append(
                Message(message_type=MessageType.WAIT, channel=default_channel, time=padding_length - current_length))

    def set_channel(self, channel: int) -> None:
        for msg in self._messages:
            msg.channel = channel

    def split(self, capacities: list[int]) -> list[RelativeSequence]:
        """Splits the sequence into parts of the given capacity.

        Creates up to `len(capacities) + 1` new `RelativeSequence`s, where the first `len(capacities)` entries contain
        sequences of the given capacities, while the last one contains any remaining notes. Messages at the boundaries
        of a capacity are split up and possibly reinserted at the beginning of the next sequence.

        Args:
            capacities: A list of capacities to split the sequence into.

        Returns: A list of `RelativeSequence`s of the desired size.

        """
        split_sequences = []
        working_memory = copy.copy(self._messages)

        current_sequence = RelativeSequence()
        open_messages = dict()

        # Try to split current sequence at given point
        for capacity in capacities:
            next_sequence = RelativeSequence()
            next_sequence_queue = []
            remaining_capacity = capacity

            while remaining_capacity >= 0:
                # Check if end-of-sequence was reached prematurely
                if len(working_memory) == 0:
                    if len(current_sequence._messages) > 0:
                        split_sequences.append(current_sequence)
                        current_sequence = next_sequence
                    break

                # Retrieve next message
                msg = working_memory.pop(0)

                # Check messages, if capacity 0 add to next sequence for most of them
                if msg.message_type == MessageType.NOTE_ON:
                    if remaining_capacity > 0:
                        current_sequence.add_message(msg)
                        open_messages[msg.note] = msg
                    else:
                        next_sequence_queue.append(msg)
                # For stop messages, add them to the current sequence
                elif msg.message_type == MessageType.NOTE_OFF:
                    current_sequence.add_message(msg)
                    open_messages.pop(msg.note, None)
                elif msg.message_type == MessageType.WAIT:
                    # Can add message in entirety
                    if msg.time <= remaining_capacity:
                        remaining_capacity -= msg.time
                        current_sequence.add_message(msg)
                    # Have to split message
                    else:
                        carry_time = msg.time - remaining_capacity

                        if remaining_capacity > 0:
                            current_sequence.add_message(
                                Message(message_type=MessageType.WAIT, channel=msg.channel, time=remaining_capacity))

                        for key, value in open_messages.items():
                            current_sequence.add_message(
                                Message(message_type=MessageType.NOTE_OFF, channel=value.channel, note=value.note))
                            next_sequence_queue.append(
                                Message(message_type=MessageType.NOTE_ON, channel=value.channel, note=value.note,
                                        velocity=value.velocity))

                        next_sequence_queue.append(
                            Message(message_type=MessageType.WAIT, channel=msg.channel, time=carry_time))

                        if len(current_sequence._messages) > 0:
                            split_sequences.append(current_sequence)
                        working_memory[0:0] = next_sequence_queue
                        current_sequence = next_sequence
                        break
                else:
                    if remaining_capacity > 0:
                        current_sequence.add_message(msg)
                    else:
                        next_sequence_queue.append(msg)

        # Check if still capacity left
        if len(working_memory) > 0:
            current_sequence._messages.extend([msg for msg in working_memory])

        # Add current sequence if it is not empty
        if len(current_sequence._messages) > 0:
            split_sequences.append(current_sequence)

        return split_sequences

    def scale(self, factor, meta_sequence=None) -> None:
        """Stretches the sequence by the given factor.

        Args:
            factor: Factor to stretch by.
            meta_sequence: Sequence containing the time signatures to apply.

        """
        if factor > 1:
            if not (factor * 1.0).is_integer():
                raise SequenceException("Factor results in non-integer scaling")
        else:
            if not (1 / factor).is_integer():
                raise SequenceException("Factor results in non-integer scaling")

        # Normal case, simply multiply duration
        if factor == 1:
            return
        if factor > 1:
            for msg in self._messages:
                if msg.message_type == MessageType.WAIT:
                    msg.time = msg.time * factor
        # Handle special case, have to consider time signatures
        else:
            from scoda.sequences.sequence import Sequence

            modified_messages = []
            sequence = Sequence(relative_sequence=self)

            if meta_sequence is None:
                meta_sequence = sequence

            amount_consecutive_bars = 1 / factor
            bars = Sequence.sequences_split_bars(
                [sequence, meta_sequence], meta_track_index=1, quantise_note_lengths=False)[0]

            bar_index = 0

            # Handle each bar
            while bar_index < len(bars):
                current_bar = bars[bar_index]
                consecutive_bars = [current_bar]

                # Get all consecutive bars in chunk
                for i in range(1, int(amount_consecutive_bars)):
                    if bar_index + i < len(bars):
                        consecutive_bars.append(bars[bar_index + i])

                # Check if all have same time signature
                if all(cbar.time_signature_numerator == current_bar.time_signature_numerator and
                       cbar.time_signature_denominator == current_bar.time_signature_denominator
                       for cbar in consecutive_bars):
                    for msg in [msg for cbar in consecutive_bars for msg in cbar.sequence.rel._messages]:
                        if msg.message_type == MessageType.WAIT:
                            msg.time = msg.time * factor

                        modified_messages.append(msg)

                    bar_index += len(consecutive_bars)
                # Not all have same time signature
                else:
                    for msg in current_bar.sequence.rel._messages:
                        if msg.message_type == MessageType.WAIT:
                            msg.time = msg.time * factor
                        elif msg.message_type == MessageType.TIME_SIGNATURE:
                            if msg.numerator % (1 / factor) == 0:
                                msg.numerator = int(msg.numerator * factor)
                            else:
                                msg.denominator = int(msg.denominator * (1 / factor))

                        modified_messages.append(msg)

                    bar_index += 1

            self._messages = modified_messages
            self.normalise_relative()

    def transpose(self, transpose_by: int) -> bool:
        """Transposes the sequence by the given amount.

        If the lower or upper bound is undercut over exceeded, these notes are transposed by an octave each.

        Args:
            transpose_by: Half-tone steps to transpose by.

        Returns: `True` if at least one note had to be shifted due to it otherwise being out of bounds.

        """
        had_to_shift = False

        for msg in self._messages:
            if msg.message_type == MessageType.NOTE_ON or msg.message_type == MessageType.NOTE_OFF:
                msg.note += transpose_by
                while msg.note < NOTE_LOWER_BOUND:
                    had_to_shift = True
                    msg.note += 12
                while msg.note > NOTE_UPPER_BOUND:
                    had_to_shift = True
                    msg.note -= 12
            elif msg.message_type == MessageType.KEY_SIGNATURE:
                msg.key = Key.transpose_key(msg.key, transpose_by)

        return had_to_shift

    # Misc. Methods

    def is_empty(self) -> bool:
        """Checks if the sequence is empty, i.e., no notes are opened.

        Returns: `True` if the sequence is empty, `False` otherwise.

        """
        for msg in self._messages:
            if msg.message_type == MessageType.NOTE_ON:
                return False
        return True

    def get_key_signature_guess(self) -> Key:
        """Determines the best key based on which key induces the minimum amount of additional accidentals.

        Returns: The best-fitting key for this bar.

        """
        for msg in self._messages:
            if msg.message_type == MessageType.KEY_SIGNATURE:
                return msg.key
            if msg.message_type == MessageType.WAIT:
                break

        key_candidates = []
        for _ in MusicMapping.KeyNoteMapping:
            key_candidates.append(0)

        for msg in self._messages:
            if msg.message_type == MessageType.NOTE_ON:
                for i, (_, key_notes) in enumerate(MusicMapping.KeyNoteMapping.items()):
                    if Note(msg.note % 12) not in key_notes[0]:
                        key_candidates[i] += 1

        best_index = 0
        best_solution = math.inf
        best_solution_accidentals = math.inf
        key_note_mapping = list(MusicMapping.KeyNoteMapping.items())

        for i in range(0, len(key_candidates)):
            if key_candidates[i] <= best_solution:
                if key_candidates[i] < best_solution or key_note_mapping[i][1][1] < best_solution_accidentals:
                    best_index = i
                    best_solution = key_candidates[i]
                    best_solution_accidentals = key_note_mapping[i][1][1]

        guessed_key = [key for key in MusicMapping.KeyNoteMapping][best_index]
        return guessed_key

    def get_sequence_duration_relation(self) -> float:
        """Calculates the duration of the sequence in multiples of the `PPQN`.

        Returns: The duration of the sequence as a multiple of the `PPQN`.

        """
        duration = 0

        for msg in self._messages:
            if msg.message_type == MessageType.WAIT:
                duration += msg.time

        return duration / PPQN

    def to_midi_track(self) -> MidiTrack:
        """Converts the sequence to a `MidiTrack`.

        Returns: The corresponding `MidiTrack`.

        """
        track = MidiTrack()

        for msg in self._messages:
            track.messages.append(MidiMessage.parse_internal_message(msg))

        return track
