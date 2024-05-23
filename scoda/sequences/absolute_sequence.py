from __future__ import annotations

import copy
from statistics import geometric_mean
from typing import TYPE_CHECKING

from scoda.elements.message import Message
from scoda.enumerations.message_type import MessageType
from scoda.exceptions.sequence_exception import SequenceException
from scoda.misc.scoda_logging import get_logger
from scoda.misc.util import binary_insort, find_minimal_distance, regress, minmax, simple_regression, \
    get_note_durations, \
    get_tuplet_durations, get_dotted_note_durations
from scoda.sequences.abstract_sequence import AbstractSequence
from scoda.settings.settings import PPQN, DIFF_DUAL_NOTE_VALUES_UPPER_BOUND, \
    DIFF_DUAL_NOTE_VALUES_LOWER_BOUND, NOTE_VALUE_UPPER_BOUND, NOTE_VALUE_LOWER_BOUND, VALID_TUPLETS, DOTTED_ITERATIONS, \
    SCALE_LOGLIKE

if TYPE_CHECKING:
    from scoda.sequences.relative_sequence import RelativeSequence


class AbsoluteSequence(AbstractSequence):
    """Class representing a sequence with absolute message timings.
    """

    LOGGER = get_logger(__name__)

    # General Methods

    def __init__(self) -> None:
        super().__init__()

    def __copy__(self) -> AbsoluteSequence:
        cpy = AbsoluteSequence()

        for message in self.messages:
            cpy.messages.append(copy.copy(message))

        return cpy

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, AbsoluteSequence):
            return False

        self_array = self.get_message_time_pairings()
        other_array = o.get_message_time_pairings()

        for self_pair, other_pair in zip(self_array, other_array):
            if self_pair[0].time != other_pair[0].time or \
                    self_pair[0].note != other_pair[0].note or \
                    self_pair[1].time != other_pair[1].time:
                return False

        return True

    # Basic Methods

    def add_message(self, msg: Message) -> None:
        """Adds the given message to the current sequence."""
        binary_insort(self.messages, msg)

    def _add_message_unsorted(self, msg: Message) -> None:
        """Adds the given message to the current sequence."""
        self.messages.append(msg)

    def cutoff(self, maximum_length, reduced_length) -> None:
        """Reduces the length of all notes longer than the maximum length to this value.

        Args:
            maximum_length: Maximum note length allowed in this sequence.
            reduced_length: The length violating notes are assigned.

        """
        note_array = self.get_message_time_pairings()

        for entry in note_array:
            if len(entry) == 1:
                if not entry[0].message_type == MessageType.NOTE_ON:
                    raise SequenceException("Cutoff: Note was closed without having been opened.")
                self.add_message(
                    Message(message_type=MessageType.NOTE_OFF, note=entry[0].note, time=entry[0].time + maximum_length))
            else:
                if entry[1].time - entry[0].time > maximum_length:
                    entry[1].time = entry[0].time + reduced_length

        self.normalise_absolute()

    def merge(self, sequences: list[AbsoluteSequence]) -> None:
        """Merges this sequence with all the given ones.

        In case of the creation of overlapping notes, these will be combined. The earliest start and the latest end will
        be used for the newly created note.

        Args:
            sequences: The sequence to merge with this one.

        """
        for sequence in sequences:
            for msg in copy.copy(sequence.messages):
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
            quantise_parameters = get_note_durations(1, 8)
            quantise_parameters += get_tuplet_durations(quantise_parameters, 3, 2)
            step_sizes = quantise_parameters

        # List of finally quantised messages
        quantised_messages = []
        # Keep track of open messages, in order to guarantee quantisation does not smother them
        open_messages = dict()
        # Keep track of from when to when notes are played, in order to eliminate double notes
        message_timings = dict()

        for msg in self.messages:
            message_original_time = msg.time
            message_to_append = copy.copy(msg)

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
                    AbsoluteSequence.LOGGER.warning(f"Quantisation: Note {msg.note} not previously stopped.")
                    quantised_messages.append(
                        Message(message_type=MessageType.NOTE_OFF, note=msg.note, time=message_to_append.time))
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
                    note_open_timing = open_messages.pop(msg.note, None)

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

        self.messages = quantised_messages
        self.normalise_absolute()

    def quantise_note_lengths(self, possible_durations=None, standard_length=PPQN, do_not_extend=False) -> None:
        """Quantises the note lengths of this sequence, only affecting the ending of the notes.

        Quantises notes to the given values, ensuring that all notes are of one of the sizes defined by the
        parameters. See `scoda.utils.utils.get_note_durations`, `scoda.utils.utils.get_tuplet_durations` and
        `scoda.utils.utils.get_dotted_note_durations` for generating the `possible_durations` array. Tries to shorten
        or extend the end of each note in such a way that the note duration is exactly one of the values given in
        `possible_durations`. If this is not possible (e.g., due to an overlap with another note that would occur),
        the note that can neither be shortened nor lengthened will be removed from the sequence. Note that this is
        only the case if the note was shorter than the smallest legal duration specified, and thus cannot be shortened.

        Args:
            possible_durations: An array containing exactly the valid note durations in ticks.
            standard_length: Note length for notes which are not closed.
            do_not_extend: Determines if notes are only allowed to be shortened, e.g., for bars.

        """
        # Construct current durations
        notes = self.get_message_time_pairings(standard_length=standard_length)
        # Track when each type of note occurs, in order to check for possible overlaps
        note_occurrences = dict()
        quantised_messages = []

        # Construct possible durations
        if possible_durations is None:
            normal_durations = get_note_durations(NOTE_VALUE_UPPER_BOUND, NOTE_VALUE_LOWER_BOUND)
            triplet_durations = []
            for valid_tuplet in VALID_TUPLETS:
                triplet_durations.extend(get_tuplet_durations(normal_durations, valid_tuplet[0], valid_tuplet[1]))
            dotted_durations = get_dotted_note_durations(normal_durations, DOTTED_ITERATIONS)
            possible_durations = normal_durations + triplet_durations + dotted_durations

        # Construct array keeping track of when each note occurs
        for pairing in notes:
            note = pairing[0].note
            note_occurrences.setdefault(note, [])
            note_occurrences[note].append(pairing)

        # Handle each note, pairing consists of start and stop message
        for i, pairing in enumerate(notes):
            note = pairing[0].note
            current_duration = pairing[1].time - pairing[0].time
            valid_durations = copy.copy(possible_durations)

            # Check if the current note is not the last note, in this case clashes with a next note could exist
            index = note_occurrences[note].index(pairing)
            if index != len(note_occurrences[note]) - 1:
                possible_next_pairing = note_occurrences[note][index + 1]

                # Possible durations contains the same as valid durations at the beginning
                for possible_duration in possible_durations:
                    possible_correction = possible_duration - current_duration

                    # If we cannot extend the note, remove the time from possible times
                    if pairing[1].time + possible_correction > possible_next_pairing[0].time:
                        valid_durations.remove(possible_duration)

            # If we are not allowed to extend note lengths, remove all positive corrections
            for possible_duration in possible_durations:
                possible_correction = possible_duration - current_duration

                if possible_correction > 0 and do_not_extend and possible_duration in valid_durations:
                    valid_durations.remove(possible_duration)

            # Check if we have to remove the note
            if len(valid_durations) == 0:
                notes[i] = []
            else:
                current_duration = pairing[1].time - pairing[0].time
                best_fit = valid_durations[find_minimal_distance(current_duration, valid_durations)]
                correction = best_fit - current_duration
                pairing[1].time += correction

        for pairing in notes:
            quantised_messages.extend(pairing)

        for msg in self.messages:
            if msg.message_type is not MessageType.NOTE_ON and msg.message_type is not MessageType.NOTE_OFF:
                quantised_messages.append(msg)

        self.messages = quantised_messages
        self.normalise_absolute()

    def sort(self) -> None:
        """Sorts the sequence according to the timings of the messages.

        This sorting procedure is stable, if two messages occurred in a specific order at the same time before the sort,
        they will occur in this order after the sort.

        """
        self.messages.sort(key=lambda x: (x.time, x.message_type, x.note))

    # Misc. Methods

    def get_message_time_pairings(self, message_types: list[MessageType] = None, standard_length=PPQN,
                                  impute_notes=True) -> list[
        list[Message]]:
        """Creates an ordered list containing lists of messages of the given types.
        These lists contain all entries for messages that belong together, e.g., open and close note messages.

        Args:
            message_types: All message types to include.
            standard_length: The length used for notes that have not been closed.
            impute_notes: If unclosed notes should be closed and unopened ones should be ignored.

        Returns: An array of tuples of two messages constituting a note.

        """
        if message_types is None:
            message_types = [MessageType.NOTE_ON, MessageType.NOTE_OFF]

        self.normalise_absolute()

        open_messages = dict()
        notes: [[]] = []
        i = 0

        # Collect notes
        for msg in self.messages:
            if msg.message_type in message_types:
                # Add notes to open messages
                if msg.message_type == MessageType.NOTE_ON:
                    if msg.note in open_messages and impute_notes:
                        AbsoluteSequence.LOGGER.warning(
                            f"Time Pairings: Note {msg.note} at time {msg.time} not previously stopped.")
                        index = open_messages.pop(msg.note)
                        notes[index].append(Message(message_type=MessageType.NOTE_OFF, note=msg.note, time=msg.time))

                    open_messages[msg.note] = i
                    notes.insert(i, [msg])
                    i += 1

                # Add closing message to fitting open message
                elif msg.message_type == MessageType.NOTE_OFF:
                    if msg.note not in open_messages and impute_notes:
                        AbsoluteSequence.LOGGER.warning(
                            f"Time Pairings: Note {msg.note} at time {msg.time} not previously started.")
                    else:
                        index = open_messages.pop(msg.note)
                        notes[index].append(msg)

                else:
                    notes.insert(i, [msg])
                    i += 1

        # Check unclosed notes
        for pairing in notes:
            if len(pairing) == 1 and pairing[0].message_type == MessageType.NOTE_ON and impute_notes:
                pairing.append(Message(message_type=MessageType.NOTE_OFF, time=pairing[0].time + standard_length))

        return notes

    def get_message_timings_of_type(self, message_types: list[MessageType]) -> list[tuple[int, Message]]:
        """Searches for messages that fit one of the given types.

        Args:
            message_types: Which message types to search for.

        Returns: A list containing the found messages and their absolute points in time.

        """
        timings = []

        for msg in self.messages:
            if msg.message_type in message_types:
                timings.append((msg.time, msg))

        return timings

    def get_sequence_duration(self) -> int:
        """Calculates the overall duration of this sequence, given in ticks.

        Returns: The duration of this sequence.

        """
        return self.messages[-1].time

    def to_relative_sequence(self) -> RelativeSequence:
        """Converts this AbsoluteSequence to a RelativeSequence.

        Returns: The relative representation of this sequence.

        """
        from scoda.sequences.relative_sequence import RelativeSequence
        relative_sequence = RelativeSequence()
        current_point_in_time = 0

        for msg in self.messages:
            time = msg.time
            # Check if we have to add wait messages
            if time > current_point_in_time:
                relative_sequence.add_message(
                    Message(message_type=MessageType.WAIT, time=time - current_point_in_time))
                current_point_in_time = time

            if msg.message_type != MessageType.INTERNAL:
                message_to_add = copy.copy(msg)
                message_to_add.time = None
                relative_sequence.add_message(message_to_add)

        return relative_sequence

    # Difficulty Methods

    def diff_note_values(self) -> float:
        """Calculates complexity of the piece regarding the geometric mean of the note values.

        Calculates the geometric mean based on all occurring notes in this sequence and then applies linear scaling
        to it. Returns a value from 0 to 1, where 0 indicates low difficulty. If no notes exist in this sequence,
        the lowest complexity rating is returned.

        Returns: A value from 0 (low difficulty) to 1 (high difficulty).

        """
        notes = self.get_message_time_pairings()
        durations = []

        for pairing in notes:
            durations.append(pairing[1].time - pairing[0].time)

        if len(durations) == 0:
            durations.append(DIFF_DUAL_NOTE_VALUES_LOWER_BOUND)

        mean = geometric_mean(durations)
        bound_mean = minmax(0, 1,
                            simple_regression(DIFF_DUAL_NOTE_VALUES_UPPER_BOUND, 1, DIFF_DUAL_NOTE_VALUES_LOWER_BOUND,
                                              0, mean))

        return minmax(0, 1, bound_mean)

    def diff_rhythm(self) -> float:
        """Calculates difficulty based on the rhythm of the sequence.

        For this calculation, note values are weighted by checking if they are normal values, dotted, or tuplet ones.

        Returns: A value from 0 (low difficulty) to 1 (high difficulty).

        """
        notes = self.get_message_time_pairings()

        # If sequence is empty, return easiest difficulty
        if len(notes) == 0:
            return 0

        note_durations = get_note_durations(NOTE_VALUE_UPPER_BOUND, NOTE_VALUE_LOWER_BOUND)

        tuplets = []
        for tuplet_duration in VALID_TUPLETS:
            tuplets.append(get_tuplet_durations(note_durations, tuplet_duration[0], tuplet_duration[1]))

        dotted_durations = get_dotted_note_durations(note_durations, DOTTED_ITERATIONS)

        notes_regular = []
        notes_dotted = []
        notes_tuplets = []

        for note in notes:
            duration = note[1].time - note[0].time

            if duration in note_durations:
                notes_regular.append(note)
            elif any(duration in x for x in tuplets):
                notes_tuplets.append(note)
            elif duration in dotted_durations:
                notes_dotted.append(note)
            else:
                AbsoluteSequence.LOGGER.warning(f"Difficulty Rhythm: Note value {duration} not in known values.")

        rhythm_occurrences = 0

        rhythm_occurrences += len(notes_dotted) * 0.5
        rhythm_occurrences += len(notes_tuplets) * 1

        unscaled_difficulty = minmax(0, 1, rhythm_occurrences / len(notes))
        scaled_difficulty = regress(unscaled_difficulty, SCALE_LOGLIKE)

        return minmax(0, 1, scaled_difficulty)
