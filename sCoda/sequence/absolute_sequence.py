from __future__ import annotations

import copy
import logging
from statistics import geometric_mean
from typing import TYPE_CHECKING

from sCoda.elements.message import Message, MessageType
from sCoda.sequence.abstract_sequence import AbstractSequence
from sCoda.settings import PPQN, SCALE_X3, DIFF_NOTE_VALUES_UPPER_BOUND, \
    DIFF_NOTE_VALUES_LOWER_BOUND, NOTE_VALUE_UPPER_BOUND, NOTE_VALUE_LOWER_BOUND, VALID_TUPLETS, DOTTED_ITERATIONS, \
    SCALE_LOGLIKE
from sCoda.util.util import b_insort, find_minimal_distance, regress, minmax, simple_regression, get_note_durations, \
    get_tuplet_durations, get_dotted_note_durations

if TYPE_CHECKING:
    from sCoda.sequence.relative_sequence import RelativeSequence


class AbsoluteSequence(AbstractSequence):
    """ Class representing a sequence with absolute message timings.

    """

    def __init__(self) -> None:
        super().__init__()

    def add_message(self, msg: Message) -> None:
        b_insort(self.messages, msg)

    def diff_note_values(self) -> float:
        """ Calculates complexity of the piece regarding to the geometric mean of the note values.

        Calculates the geometric mean based on all occurring notes in this sequence and then applies linear scaling
        to it. Returns a value from 0 to 1, where 0 indicates low difficulty. If no notes exist in this sequence,
        the lowest complexity rating is returned.

        Returns: A value from 0 (low difficulty) to 1 (high difficulty)

        """
        notes = self._get_absolute_note_array()
        durations = []

        for pairing in notes:
            durations.append(pairing[1].time - pairing[0].time)

        if len(durations) == 0:
            durations.append(DIFF_NOTE_VALUES_LOWER_BOUND)

        mean = geometric_mean(durations)
        bound_mean = minmax(0, 1,
                            simple_regression(DIFF_NOTE_VALUES_UPPER_BOUND, 1, DIFF_NOTE_VALUES_LOWER_BOUND, 0, mean))
        scaled_mean = regress(bound_mean, SCALE_X3)

        return minmax(0, 1, scaled_mean)

    def diff_note_classes(self) -> float:
        """ Calculates difficulty of the sequence based on the amount of note classes (different notes played) in
        relation to the overall amount of messages.

        Returns: A value from 0 (low difficulty) to 1 (high difficulty)

        """
        notes = self._get_absolute_note_array()
        note_classes = []

        for pairing in notes:
            if pairing[0].note not in note_classes:
                note_classes.append(pairing[0].note)

        relation = len(note_classes) / len(notes)
        scaled_relation = regress(relation, SCALE_X3)

        return minmax(0, 1, scaled_relation)

    def diff_rhythm(self) -> float:
        """ Calculates difficulty based on the rhythm of the sequence.

        For this calculation, note values are weighted by checking if they are normal values, dotted, or tuplet ones.

        Returns: A value from 0 (low difficulty) to 1 (high difficulty)

        """
        notes = self._get_absolute_note_array()

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
                logging.warning("Note value not covered")

        rhythm_occurrences = 0

        rhythm_occurrences += len(notes_dotted) * 0.5
        rhythm_occurrences += len(notes_tuplets) * 1

        difficulty_unscaled = minmax(0, 1, rhythm_occurrences / len(notes))
        difficulty_scaled = minmax(0, 1, regress(difficulty_unscaled, SCALE_LOGLIKE))

        return difficulty_scaled

    def get_timing_of_message_type(self, message_type: MessageType) -> [int]:
        """ Searches for the given message type and stores the time of all matching messages in the output array.

        Args:
            message_type: Which message type to search for

        Returns: An array containing the absolute points in time of occurrence of the found messages

        """
        timings = []

        for msg in self.messages:
            if msg.message_type == message_type:
                timings.append(msg.time)

        return timings

    def merge(self, sequences: [AbsoluteSequence]) -> None:
        """ Merges this sequence with all the given ones.

        Args:
            sequences: The sequences to merge with this one

        Returns: The sequence that contains all messages of this and the given sequences, conserving the timings

        """
        for sequence in sequences:
            for msg in copy.copy(sequence.messages):
                b_insort(self.messages, msg)

    def quantise(self, step_sizes: [int]) -> None:
        """ Quantises the sequence to a given grid.

        Quantises the sequence stored in this object according to the given step sizes. These step sizes determine the
        size of the underlying grid, e.g. a step size of 3 would allow for messages to be placed at multiples of 3
        ticks. Note that the induced length of the notes is dependent on the `PPQN`, e.g., with a `PPQN` of 24,
        a step size of 3 would be equivalent to a grid conforming to thirty-second notes. If there exists a tie between
        two grid boundaries, these are first resolved by whether the quantisation would prevent a note-length of 0,
        then by the order of the `step_sizes` array. The result of this operation is that all messages of this
        sequence have a time divisible by one of the values in `step_sizes`. If the quantisation resulted in two
        notes overlapping, the second note will be removed. See `sCoda.util.util.get_note_durations`,
        `sCoda.util.util.get_tuplet_durations` and `sCoda.util.util.get_dotted_note_durations` for generating the
        `step_sizes` array.

        Args:
            step_sizes: Array of numbers corresponding to divisors of the grid length

        """
        quantised_messages = []
        # Keep track of open messages, in order to guarantee quantisation does not smother them
        open_messages = dict()
        # Keep track of from when to when notes are played, in order to eliminate double notes
        message_timings = dict()

        for msg in self.messages:
            original_time = msg.time
            message_to_append = copy.copy(msg)

            # Positions the note would land at according to each of the quantisation parameters
            positions_left = [(original_time // step_size) * step_size for step_size in step_sizes]
            positions_right = [positions_left[i] + step_sizes[i] for i in range(0, len(step_sizes))]

            possible_positions = positions_left + positions_right
            valid_positions = []

            # Consider quantisations that could smother notes
            if msg.message_type == MessageType.note_on:
                # Sanity check
                if msg.note in open_messages:
                    logging.warning(f"Note {msg.note} not previously stopped, inserting stop message")
                    quantised_messages.append(Message(message_type=MessageType.note_off, note=msg.note, time=msg.time))
                    open_messages.pop(msg.note, None)
                    message_timings[msg.note].append(message_to_append.time)

                valid_positions += possible_positions
                message_to_append.time = valid_positions[find_minimal_distance(original_time, valid_positions)]

                # Can open new note
                if msg.note not in message_timings \
                        or not message_to_append.time < message_timings[msg.note][1]:
                    open_messages[msg.note] = message_to_append.time
                    message_timings[msg.note] = [message_to_append.time]
                # Note would overlap with other, existing note
                else:
                    message_to_append = None
            elif msg.message_type == MessageType.note_off:
                # Message is currently open, have to quantize
                if msg.note in open_messages:
                    note_open_timing = open_messages.pop(msg.note, None)

                    # Add possible positions for stop messages, making sure the belonging note is not smothered
                    for position in possible_positions:
                        if not position - note_open_timing <= 0:
                            valid_positions.append(position)

                    # Valid positions will always exist, since if order held before quantisation, same will hold after
                    message_to_append.time = valid_positions[find_minimal_distance(original_time, valid_positions)]
                    message_timings[msg.note].append(message_to_append.time)
                # Message is not currently open (e.g., if start message was removed due to an overlap)
                else:
                    message_to_append = None
            else:
                valid_positions += possible_positions
                message_to_append.time = valid_positions[find_minimal_distance(original_time, valid_positions)]

            if message_to_append is not None:
                quantised_messages.append(message_to_append)

        self.messages = quantised_messages
        self.sort()

    def quantise_note_lengths(self, possible_durations, standard_length=PPQN) -> None:
        """ Quantises the note lengths of this sequence, only affecting the ending of the notes.

        Quantises notes to the given values, ensuring that all notes are of one of the sizes defined by the
        parameters. See `sCoda.util.util.get_note_durations`, `sCoda.util.util.get_tuplet_durations` and
        `sCoda.util.util.get_dotted_note_durations` for generating the `possible_durations` array. Tries to shorten
        or extend the end of each note in such a way that the note duration is exactly one of the values given in
        `possible_durations`. If this is not possible (e.g., due to an overlap with another note that would occur),
        the note that can neither be shortened nor lengthened will be removed from the sequence. Note that this is
        only the case if the note was shorter than the smallest legal duration specified, and thus cannot be shortened.

        Args:
            possible_durations: An array containing exactly the valid note durations in ticks
            standard_length: Note length for notes which are not closed

        """
        # Construct possible durations
        notes = self._get_absolute_note_array(standard_length=standard_length)
        # Track when each type of note occurs, in order to check for possible overlaps
        note_occurrences = dict()
        quantised_messages = []

        # Construct array keeping track of when each note occurs
        for pairing in notes:
            note = pairing[0].note
            note_occurrences.setdefault(note, [])
            note_occurrences[note].append(pairing)

        # Handle each note, pairing consists of start and stop message
        for i, pairing in enumerate(notes):
            note = pairing[0].note
            valid_durations = copy.copy(possible_durations)

            # Check if there exists a clash with the following note
            index = note_occurrences[note].index(pairing)
            if index != len(note_occurrences[note]) - 1:
                possible_next_pairing = note_occurrences[note][index + 1]
                current_duration = pairing[1].time - pairing[0].time

                # Possible durations contains the same as valid durations at the beginning
                for possible_duration in possible_durations:
                    possible_correction = possible_duration - current_duration

                    # If we cannot extend the note, remove the time from possible times
                    if pairing[1].time + possible_correction > possible_next_pairing[0].time:
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
            if msg.message_type is not MessageType.note_on and msg.message_type is not MessageType.note_off:
                quantised_messages.append(msg)

        self.messages = quantised_messages
        self.sort()

    def sort(self) -> None:
        """ Sorts the sequence according to the timings of the messages.

        This sorting procedure is stable, if two messages occurred in a specific order at the same time before the sort,
        they will occur in this order after the sort.

        """
        self.messages.sort(key=lambda x: x.time)

    def to_relative_sequence(self) -> RelativeSequence:
        """ Converts this AbsoluteSequence to a RelativeSequence

        Returns: The relative representation of this sequence

        """
        from sCoda.sequence.relative_sequence import RelativeSequence
        relative_sequence = RelativeSequence()
        current_point_in_time = 0

        for msg in self.messages:
            time = msg.time
            # Check if we have to add wait messages
            if time > current_point_in_time:
                relative_sequence.add_message(
                    Message(message_type=MessageType.wait, time=time - current_point_in_time))
                current_point_in_time = time

            message_to_add = copy.copy(msg)
            message_to_add.time = None
            relative_sequence.add_message(message_to_add)

        return relative_sequence

    def _get_absolute_note_array(self, standard_length=PPQN) -> []:
        open_messages = dict()
        notes: [[]] = []
        i = 0

        # Collect notes
        for msg in self.messages:
            # Add notes to open messages
            if msg.message_type == MessageType.note_on:
                if msg.note in open_messages:
                    logging.warning(
                        f"Note {msg.note} at time {msg.time} not previously stopped, inserting stop message")
                    index = open_messages.pop(msg.note)
                    notes[index].append(Message(message_type=MessageType.note_off, note=msg.note, time=msg.time))

                open_messages[msg.note] = i
                notes.insert(i, [msg])
                i += 1

            # Add closing message to fitting open message
            elif msg.message_type == MessageType.note_off:
                if msg.note not in open_messages:
                    logging.warning(f"Note {msg.note} at time {msg.time} not previously started, skipping")
                else:
                    index = open_messages.pop(msg.note)
                    notes[index].append(msg)

        # Check unclosed notes
        for pairing in notes:
            if len(pairing) == 1:
                pairing.append(Message(message_type=MessageType.wait, time=pairing[0].time + standard_length))

        return notes
