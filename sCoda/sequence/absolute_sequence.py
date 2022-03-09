from __future__ import annotations

import copy
import logging
from typing import TYPE_CHECKING

from sCoda.elements.message import Message, MessageType
from sCoda.sequence.abstract_sequence import AbstractSequence
from sCoda.settings import PPQN
from sCoda.util.util import b_insort, find_minimal_distance

if TYPE_CHECKING:
    from sCoda.sequence.relative_sequence import RelativeSequence


class AbsoluteSequence(AbstractSequence):
    """ Class representing a sequence with absolute message timings.

    """

    def __init__(self) -> None:
        super().__init__()

    def add_message(self, msg: Message) -> None:
        b_insort(self.messages, msg)

    def diff_message_values(self) -> float:
        notes = self._get_absolute_note_array()

    def merge(self, sequences: [AbsoluteSequence]) -> None:
        """ Merges this sequence with all the given ones.

        Args:
            sequences: The sequences to merge with this one

        Returns: The sequence that contains all messages of this and the given sequences, conserving the timings

        """
        for sequence in sequences:
            for msg in copy.copy(sequence.messages):
                b_insort(self.messages, msg)

    def quantise(self, divisors: [int]) -> None:
        """ Quantises the sequence to a given grid.

        Quantises the sequence stored in this object according to the given divisors. These divisors determine the
        step size of the grid, e.g., an entry of 8 would correspond in a grid size of `PPQN / 8`. If `PPQN` were 24,
        the grid would support the length 3, in this example thirty-secondth notes. If there exists a tie between two
        grid boundaries, these are first resolved by whether the quantisation would prevent a note-length of 0,
        then by the order of the divisors array. The result of this operation is that all messages of this sequence
        have a time divisible by `PPQN / divisor`, for all entries in divisors. If the quantisation resulted in
        two notes overlapping, the second note will be removed.

        Args:
            divisors: Array of number by which the `PPQN` will be divided to determine possible step-size for the grid

        """
        quantised_messages = []
        # Keep track of open messages, in order to guarantee quantisation does not smother them
        open_messages = dict()
        # Keep track of from when to when notes are played, in order to eliminate double notes
        message_timings = dict()

        for msg in self.messages:
            original_time = msg.time
            message_to_append = copy.copy(msg)

            # Size of the steps for each of the quantisation parameters
            step_sizes = [PPQN / i for i in divisors]

            # Positions the note would land at according to each of the quantisation parameters
            positions_left = [(original_time // step_size) * step_size for step_size in step_sizes]
            positions_right = [positions_left[i] + step_sizes[i] for i in range(0, len(divisors))]

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

        # TODO
        Quantises notes to the given values, ensuring that all notes are of one of the sizes defined by the
        parameters. The upper bound multiplier determines the longest possible note value, in terms of the `PPQN`. An
        upper bound of 2, e.g., would result in a maximum note length of `2 * PPQN`, meaning half-notes. The same holds
        for the lower bound, where the `PPQN` is divided by it. Furthermore, the option of having dotted notes is
        given, where each iteration adds all (possible) notes dotted up to the iteration amount, e.g., an iteration
        value of 2 would result in two-dotted notes being accepted. Note that only integer results are accepted,
        which in conjunction with the value for the `PPQN` can result in some values being rejected.

        Args:
            possible_durations: An array containing exactly the valid note durations in ticks
            standard_length: Note length for notes which are not closed

        """
        # Construct possible durations
        notes = self._get_absolute_note_array(standard_length=standard_length)
        note_occurrences = dict()
        quantised_messages = []

        for pairing in notes:
            note = pairing[0].note
            note_occurrences.setdefault(note, [])
            note_occurrences[note].append(pairing)

        for i, pairing in enumerate(notes):
            note = pairing[0].note
            valid_durations = copy.copy(possible_durations)

            # Check if there exists a clash with the following note
            index = note_occurrences[note].index(pairing)
            if index != len(note_occurrences[note]) - 1:
                print(f"{pairing[0].note}")
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
                best_fit = possible_durations[find_minimal_distance(current_duration, valid_durations)]
                correction = best_fit - current_duration
                pairing[1].time += correction
                print(f"Note: {pairing[0].note} Duration: {current_duration}, Valid: {valid_durations}, chosen: {best_fit}, correction: {correction}, previous: {pairing[1].time - correction} result: {pairing[1].time}")

        for pairing in notes:
            quantised_messages.extend(pairing)

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

    @staticmethod
    def _get_tracks_from_notes(notes):
        tracks = []
