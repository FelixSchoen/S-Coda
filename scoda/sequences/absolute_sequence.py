from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from scoda.elements.message import Message
from scoda.enumerations.message_type import MessageType
from scoda.exceptions.sequence_exception import SequenceException
from scoda.misc.scoda_logging import get_logger
from scoda.misc.util import binary_insort, find_minimal_distance, get_default_step_sizes, get_default_note_values
from scoda.sequences.abstract_sequence import AbstractSequence
from scoda.settings.settings import PPQN

if TYPE_CHECKING:
    from scoda.sequences.relative_sequence import RelativeSequence


class AbsoluteSequence(AbstractSequence):
    """Class representing a sequence with absolute message timings.
    """

    LOGGER = get_logger(__name__)

    # General Methods

    def __init__(self, messages: list = None) -> None:
        super().__init__(messages=messages)

    def __eq__(self, o: object) -> bool:
        return self.equals(o)

    def to_relative_sequence(self) -> RelativeSequence:
        """Converts this AbsoluteSequence to a RelativeSequence.

        Returns: The relative representation of this sequence.

        """
        from scoda.sequences.relative_sequence import RelativeSequence
        relative_sequence = RelativeSequence()
        current_point_in_time = 0

        for msg in self._messages:
            time = msg.time
            # Check if we have to add wait messages
            if time > current_point_in_time:
                relative_sequence.add_message(
                    Message(message_type=MessageType.WAIT, channel=msg.channel, time=time - current_point_in_time))
                current_point_in_time = time

            if msg.message_type != MessageType.INTERNAL:
                message_to_add = msg.copy()
                message_to_add.time = None
                relative_sequence.add_message(message_to_add)

        return relative_sequence

    # Basic Methods

    def add_message(self, msg: Message) -> None:
        """Adds the given message to the current sequence."""
        binary_insort(self._messages, msg)

    def _add_message_unsorted(self, msg: Message) -> None:
        """Adds the given message to the current sequence."""
        self._messages.append(msg)

    def cutoff(self, maximum_length, reduced_length) -> None:
        """Reduces the length of all notes longer than the maximum length to this value.

        Args:
            maximum_length: Maximum note length allowed in this sequence.
            reduced_length: The length violating notes are assigned.

        """
        channel_pairings = self.get_message_pairings()

        for message_pairings in channel_pairings.values():
            for message_pairing in message_pairings:
                if len(message_pairing) == 1:
                    if not message_pairing[0].message_type == MessageType.NOTE_ON:
                        raise SequenceException("Cutoff: Note was closed without having been opened.")
                    self.add_message(
                        Message(message_type=MessageType.NOTE_OFF, channel=message_pairing[0].channel,
                                note=message_pairing[0].note,
                                time=message_pairing[0].time + maximum_length))
                else:
                    if message_pairing[1].time - message_pairing[0].time > maximum_length:
                        message_pairing[1].time = message_pairing[0].time + reduced_length

        self.normalise_absolute()

    def equals(self,
               other: object,
               ignore_channel: bool = False,
               ignore_time_signature: bool = False,
               ignore_key_signature: bool = False,
               ignore_velocity: bool = False) -> bool:
        """Checks if this sequence is equal to another one.

        Args:
            other: The other sequence to compare with.
            ignore_channel: If the channel should be ignored.
            ignore_time_signature: If the time signature should be ignored.
            ignore_key_signature: If the key signature should be ignored.
            ignore_velocity: If the velocity should be ignored

        Returns: True if the sequences are equal, False otherwise.

        """
        if not isinstance(other, AbsoluteSequence):
            return False

        # Construct pairings
        message_types = [MessageType.NOTE_ON, MessageType.NOTE_OFF,
                         MessageType.TIME_SIGNATURE, MessageType.KEY_SIGNATURE]

        if ignore_time_signature:
            message_types.remove(MessageType.TIME_SIGNATURE)
        if ignore_key_signature:
            message_types.remove(MessageType.KEY_SIGNATURE)

        self_pairings = self.get_interleaved_message_pairings(message_types=message_types)
        other_pairings = other.get_interleaved_message_pairings(message_types=message_types)

        if not len(self_pairings) == len(other_pairings):
            return False

        for self_pair, other_pair in zip(self_pairings, other_pairings):
            self_channel = self_pair[0]
            other_channel = other_pair[0]

            # Compare channels
            if self_channel != other_channel and not ignore_channel:
                return False

            self_msgs = self_pair[1]
            other_msgs = other_pair[1]

            self_msg = self_msgs[0]
            other_msg = other_msgs[0]

            if self_msg.message_type != other_msg.message_type:
                return False

            if self_msg.message_type == MessageType.NOTE_ON:
                self_msg_value = self_msgs[1].time - self_msg.time
                other_msg_value = other_msgs[1].time - other_msg.time

                if self_msg.note != other_msg.note or self_msg_value != other_msg_value:
                    return False
                if self_msg.velocity != other_msg.velocity and not ignore_velocity:
                    return False
            elif self_msg.message_type == MessageType.TIME_SIGNATURE:
                if self_msg.numerator != other_msg.numerator or self_msg.denominator != other_msg.denominator:
                    return False
            elif self_msg.message_type == MessageType.KEY_SIGNATURE:
                if self_msg.key != other_msg.key:
                    return False

        return True

    def merge(self, sequences: list[AbsoluteSequence]) -> None:
        """Merges this sequence with all the given ones.

        In case of the creation of overlapping notes, these will be combined. The earliest start and the latest end will
        be used for the newly created note.

        Args:
            sequences: The sequence to merge with this one.

        """
        for sequence in sequences:
            for msg in [msg for msg in sequence._messages]:
                self._add_message_unsorted(msg)

        self.normalise_absolute()

    def normalise_absolute(self) -> None:
        self.sort()

    def quantise(self, step_sizes: list[int] = None) -> None:
        """Quantises the sequence to a given grid.

        Quantises the sequence stored in this object according to the given step sizes. These step sizes determine the
        size of the underlying grid, e.g. a step size of 3 would allow for messages to be placed at multiples of 3
        ticks. Note that the induced length of the notes is dependent on the `PPQN`, e.g., with a `PPQN` of 24,
        a step size of 3 would be equivalent to a grid conforming to thirty-second notes. If there exists a tie between
        two grid boundaries, these are first resolved by whether the quantisation would prevent a note-length of 0,
        then by the order of the `step_sizes` array. The result of this operation is that all messages of this
        sequence have a time divisible by one of the values in `step_sizes`. If the quantisation resulted in two
        notes overlapping, the second note will be removed. See `scoda.utils.utils.get_note_durations`,
        `scoda.utils.utils.get_tuplet_durations` and `scoda.utils.utils.get_dotted_note_durations` for generating the
        `step_sizes` array.

        Args:
            step_sizes: Array of numbers corresponding to divisors of the grid length.

        """
        if step_sizes is None:
            step_sizes = get_default_step_sizes()

        # List of finally quantised messages
        quantised_messages = []
        # Keep track of open messages, in order to guarantee quantisation does not smother them
        open_messages = dict()
        # Keep track of from when to when notes are played, in order to eliminate double notes
        message_timings = dict()

        for msg in self._messages:
            message_original_time = msg.time
            message_to_append = msg

            # Positions the note would land at according to each of the quantisation parameters
            positions_left = [(message_original_time // step_size) * step_size for step_size in step_sizes]
            positions_right = [positions_left[i] + step_sizes[i] for i in range(0, len(step_sizes))]

            possible_positions = positions_left + positions_right
            valid_positions = []

            # Consider quantisations that could smother notes
            if msg.message_type == MessageType.NOTE_ON:
                valid_positions += possible_positions
                message_to_append.time = valid_positions[find_minimal_distance(message_original_time, valid_positions)]

                # Check if note was not yet closed
                if msg.note in open_messages:
                    AbsoluteSequence.LOGGER.info(f"Quantisation: Note {msg.note} not previously stopped.")
                    quantised_messages.append(
                        Message(message_type=MessageType.NOTE_OFF, channel=msg.channel, note=msg.note,
                                time=message_to_append.time))
                    open_messages.pop(msg.note, None)
                    message_timings[msg.note].append(message_to_append.time)

                # Check if we can open note without overlaps
                if msg.note not in message_timings \
                        or not message_to_append.time < message_timings[msg.note][1]:
                    open_messages[msg.note] = message_to_append.time
                    message_timings[msg.note] = [message_to_append.time]
                # In this case note would overlap with other, existing note
                else:
                    message_to_append = None
            elif msg.message_type == MessageType.NOTE_OFF:
                # Message is currently open, have to quantize
                if msg.note in open_messages:
                    note_open_timing = open_messages.pop(msg.note)

                    # Add possible positions for stop messages, making sure the belonging note is not smothered
                    for position in possible_positions:
                        if not position - note_open_timing <= 0:
                            valid_positions.append(position)

                    # If no valid positions exists, set note length to 0
                    if len(valid_positions) == 0:
                        valid_positions.append(note_open_timing)

                    # Valid positions will always exist, since if order held before quantisation, same will hold
                    # after, and if initially no valid position was found note length will be set to 0
                    message_to_append.time = valid_positions[
                        find_minimal_distance(message_original_time, valid_positions)]
                    message_timings[msg.note].append(message_to_append.time)

                # Message is not currently open (e.g., if start message was removed due to an overlap)
                else:
                    message_to_append = None
            else:
                valid_positions += possible_positions
                message_to_append.time = valid_positions[find_minimal_distance(message_original_time, valid_positions)]

            if message_to_append is not None:
                quantised_messages.append(message_to_append)

        # Remove smothered notes
        message_timings_with_indices = dict()
        original_indices_to_remove = []

        # Get indices of violating messages
        for i, msg in enumerate(quantised_messages):
            if msg.message_type == MessageType.NOTE_ON:
                message_timings_with_indices[msg.note] = (i, msg.time)
            elif msg.message_type == MessageType.NOTE_OFF:
                j, time = message_timings_with_indices.pop(msg.note)
                if msg.time - time <= 0:
                    original_indices_to_remove.extend([j, i])

        # Remove messages
        for index_shifter, index_to_remove in enumerate(original_indices_to_remove):
            quantised_messages.pop(index_to_remove - index_shifter)

        self._messages = quantised_messages
        self.normalise_absolute()

    def quantise_note_lengths(self, note_values=None, standard_length=PPQN, do_not_extend=False) -> None:
        """Quantises the note lengths of this sequence, only affecting the ending of the notes.

        Quantises notes to the given values, ensuring that all notes are of one of the sizes defined by the
        parameters. See `scoda.utils.utils.get_note_durations`, `scoda.utils.utils.get_tuplet_durations` and
        `scoda.utils.utils.get_dotted_note_durations` for generating the `note_values` array. Tries to shorten
        or extend the end of each note in such a way that the note duration is exactly one of the values given in
        `note_values`. If this is not possible (e.g., due to an overlap with another note that would occur),
        the note that can neither be shortened nor lengthened will be removed from the sequence. Note that this is
        only the case if the note was shorter than the smallest legal duration specified, and thus cannot be shortened.

        Args:
            note_values: An array containing exactly the valid note durations in ticks.
            standard_length: Note length for notes which are not closed.
            do_not_extend: Determines if notes are only allowed to be shortened, e.g., for bars.

        """
        # Construct possible durations
        if note_values is None:
            note_values = get_default_note_values()

        # Construct current durations
        channel_pairings = self.get_message_pairings(standard_length=standard_length)
        quantised_messages = []

        for message_pairings in channel_pairings.values():
            # Track when each type of note occurs, in order to check for possible overlaps
            note_occurrences = dict()

            # Construct array keeping track of when each note occurs
            for message_pairing in message_pairings:
                note = message_pairing[0].note
                note_occurrences.setdefault(note, [])
                note_occurrences[note].append(message_pairing)

            # Handle each note, pairing consists of start and stop message
            for i, message_pairing in enumerate(message_pairings):
                note = message_pairing[0].note
                current_duration = message_pairing[1].time - message_pairing[0].time
                valid_durations = copy.copy(note_values)

                # Check if the current note is not the last note, in this case clashes with a next note could exist
                index = note_occurrences[note].index(message_pairing)
                if index != len(note_occurrences[note]) - 1:
                    possible_next_pairing = note_occurrences[note][index + 1]

                    # Note values contains the same as valid durations at the beginning
                    for note_value in note_values:
                        possible_correction = note_value - current_duration

                        # If we cannot extend the note, remove the time from possible times
                        if message_pairing[1].time + possible_correction > possible_next_pairing[0].time:
                            valid_durations.remove(note_value)

                # If we are not allowed to extend note lengths, remove all positive corrections
                for note_value in note_values:
                    possible_correction = note_value - current_duration

                    if possible_correction > 0 and do_not_extend and note_value in valid_durations:
                        valid_durations.remove(note_value)

                # Check if we have to remove the note
                if len(valid_durations) == 0:
                    message_pairings[i] = []
                else:
                    current_duration = message_pairing[1].time - message_pairing[0].time
                    best_fit = valid_durations[find_minimal_distance(current_duration, valid_durations)]
                    correction = best_fit - current_duration
                    message_pairing[1].time += correction

            for message_pairing in message_pairings:
                quantised_messages.extend(message_pairing)

        for msg in self._messages:
            if msg.message_type is not MessageType.NOTE_ON and msg.message_type is not MessageType.NOTE_OFF:
                quantised_messages.append(msg)

        self._messages = quantised_messages
        self.normalise_absolute()

    def sort(self) -> None:
        """Sorts the sequence according to the timings of the messages.

        This sorting procedure is stable, if two messages occurred in a specific order at the same time before the sort,
        they will occur in this order after the sort.

        """
        self._messages.sort(key=lambda x: (x.time, -1 if x.channel is None else x.channel, x.message_type, x.note))

    # Misc. Methods

    def get_message_pairings(self,
                             message_types: list[MessageType] = None,
                             standard_length=PPQN,
                             impute_notes=True) -> dict[int, list[list[Message]]]:
        """Creates a dictionary where the keys correspond to channels and the items to lists of messages of the given types.
        These lists contain all entries for messages that belong together, e.g., open and close note messages.

        Args:
            message_types: All message types to include.
            standard_length: The length used for notes that have not been closed.
            impute_notes: If unclosed notes should be closed and unopened ones should be ignored.

        Returns: A dictionary of lists of messages belonging together.

        """
        if message_types is None:
            message_types = [MessageType.NOTE_ON, MessageType.NOTE_OFF]

        self.normalise_absolute()

        message_pairings = dict()
        open_messages = dict()

        # Collect notes
        for msg in self._messages:
            if msg.message_type in message_types:
                # Set defaults
                message_pairings.setdefault(msg.channel, [])
                open_messages.setdefault(msg.channel, dict())

                # Add notes to open messages
                if msg.message_type == MessageType.NOTE_ON:
                    # Check if note was not previously closed
                    if msg.note in open_messages[msg.channel] and impute_notes:
                        AbsoluteSequence.LOGGER.info(
                            f"Time Pairings: Note {msg.channel}:{msg.note} at time {msg.time} not previously stopped.")
                        index = open_messages[msg.channel].pop(msg.note)
                        message_pairings[msg.channel][index].append(
                            Message(message_type=MessageType.NOTE_OFF, channel=msg.channel, note=msg.note,
                                    time=msg.time))

                    message_pairings[msg.channel].append([msg])
                    open_messages[msg.channel][msg.note] = len(message_pairings[msg.channel]) - 1

                # Add closing message to fitting open message
                elif msg.message_type == MessageType.NOTE_OFF:
                    # Check if note was not previously started
                    if msg.channel not in open_messages or msg.note not in open_messages[msg.channel]:
                        if impute_notes:
                            AbsoluteSequence.LOGGER.info(
                                f"Time Pairings: Note {msg.channel}:{msg.note} at time {msg.time} not previously started.")
                    else:
                        index = open_messages[msg.channel].pop(msg.note)
                        message_pairings[msg.channel][index].append(msg)

                else:
                    message_pairings[msg.channel].append([msg])

        # Check unclosed notes
        for channel in message_pairings:
            for pairing in message_pairings[channel]:
                if len(pairing) == 1 and pairing[0].message_type == MessageType.NOTE_ON and impute_notes:
                    pairing.append(Message(message_type=MessageType.NOTE_OFF, channel=pairing[0].channel,
                                           note=pairing[0].note, time=pairing[0].time + standard_length))

        return message_pairings

    def get_interleaved_message_pairings(self,
                                         message_types: list[MessageType] = None,
                                         standard_length=PPQN,
                                         impute_notes=True) -> list[tuple[int, list[Message]]]:
        """Creates a list of tuples of channels and messages sorted by their absolute starting times.

        Args:
            message_types: All message types to include.
            standard_length: The length used for notes that have not been closed.
            impute_notes: If unclosed notes should be closed and unopened ones should be ignored.

        Returns: A list of channel-message pairs sorted by their start times.

        """
        interleaved_pairings = []
        channel_pairings = self.get_message_pairings(message_types=message_types,
                                                     standard_length=standard_length,
                                                     impute_notes=impute_notes)

        channel_pairings_list = list(channel_pairings.items())
        channel_cur_index = [0 for _ in range(len(channel_pairings_list))]
        channel_max_index = [len(channel_pairings_list[i][1]) for i in range(len(channel_pairings_list))]
        channel_nxt_times = [channel_pairings_list[n][1][channel_cur_index[n]][0].time
                             if channel_cur_index[n] < channel_max_index[n] else float("inf")
                             for n in range(len(channel_pairings_list))]
        channel_ids = [channel_pairings_list[i][0] for i in range(len(channel_pairings_list))]

        has_next = len(channel_pairings_list) > 0

        while has_next:
            # Build list of next times for each channel
            track_val_times = [channel_nxt_times[i] if channel_cur_index[i] < channel_max_index[i] else float('inf')
                               for i in range(len(channel_ids))]

            # Get channel ID and index of channel in list and obtain next message pairing
            next_channel_index = track_val_times.index(min(track_val_times))
            next_channel = channel_ids[next_channel_index]
            next_message_pairing = channel_pairings_list[next_channel_index][1][channel_cur_index[next_channel_index]]

            # Append message to interleaved list
            interleaved_pairings.append((next_channel, next_message_pairing))

            # Update next times and indices
            channel_cur_index[next_channel_index] += 1
            channel_nxt_times = [channel_pairings_list[n][1][channel_cur_index[n]][0].time
                                 if channel_cur_index[n] < channel_max_index[n] else float("inf")
                                 for n in range(len(channel_pairings_list))]
            has_next = any(
                channel_cur_index[i] < len(channel_pairings_list[i][1]) for i in range(len(channel_pairings_list)))

            assert next_channel == next_message_pairing[0].channel

        return interleaved_pairings

    def get_message_times_of_type(self, message_types: list[MessageType]) -> list[tuple[int, Message]]:
        """Searches for messages that fit one of the given types.

        Args:
            message_types: Which message types to search for.

        Returns: A list containing the found messages and their absolute points in time.

        """
        timings = []

        for msg in self._messages:
            if msg.message_type in message_types:
                timings.append((msg.time, msg))

        return timings

    def get_sequence_channel(self) -> int | None:
        if not self.is_channel_consistent():
            raise SequenceException("Sequence has inconsistent channels.")

        return self._messages[0].channel

    def get_sequence_duration(self) -> int:
        """Calculates the overall duration of this sequence, given in ticks.

        Returns: The duration of this sequence.

        """
        return self._messages[-1].time

    def is_channel_consistent(self) -> bool:
        """Checks if the channels of all messages in this sequence are consistent, i.e., the same.

        Returns: True if the channel numbers are consistent, False otherwise.

        """
        for msg in self._messages:
            if msg.channel != self._messages[0].channel:
                return False
        return True
