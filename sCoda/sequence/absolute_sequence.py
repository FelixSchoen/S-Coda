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

    def sort(self) -> None:
        """ Sorts the sequence according to the timings of the messages.

        This sorting procedure is stable, if two messages occurred in a specific order at the same time before the sort,
        they will occur in this order after the sort.

        """
        self.messages.sort(key=lambda x: x.time)

    def add_message(self, msg: Message) -> None:
        b_insort(self.messages, msg)

    def quantise(self, divisors: [int]) -> None:
        """ Quantises the sequence to a given grid.

        Quantises the sequence stored in this object according to the given divisors. These divisors determine the
        step size of the grid, e.g., an entry of 8 would correspond in a grid size of `PPQN / 8`. If `PPQN` were 24,
        the grid would support the length 3, in this example thirty-secondth notes. If there exists a tie between two
        grid boundaries, these are first resolved by whether the quantisation would prevent a note-length of 0,
        then by the order of the divisors array. The result of this operation is that all messages of this sequence
        have a time divisible by `PPQN / divisor`, for all entries in divisors.

        Args:
            divisors: Array of number by which the `PPQN` will be divided to determine possible step-size for the grid

        """
        quantified_messages = []
        # Keep track of open messages, in order to guarantee quantisation does not smother them
        open_messages = dict()

        for msg in self.messages:
            time = msg.time
            message_to_append = copy.copy(msg)

            # Size of the steps for each of the quantisation parameters
            step_sizes = [PPQN / i for i in divisors]

            # Positions the note would land at according to each of the quantisation parameters
            positions_left = [(time // step_size) * step_size for step_size in step_sizes]
            positions_right = [positions_left[i] + step_sizes[i] for i in range(0, len(divisors))]

            positions = positions_left + positions_right

            # Check if exact hit exists
            if time in positions_left:
                pass
            else:
                valid_positions = []

                # Consider quantisations that could smother notes
                if msg.message_type == MessageType.note_off and msg.note in open_messages:
                    note_open_timing = open_messages[msg.note]

                    # Rank those entries back, that would induce a play time of smaller equal 0
                    for position in positions:
                        if not position - note_open_timing <= 0:
                            valid_positions.append(position)

                index = find_minimal_distance(time, valid_positions)
                # Change timing of message to append
                message_to_append.time = positions[index]

            # Keep track of open notes
            if msg.message_type == MessageType.note_on:
                open_messages[msg.note] = msg.time
            elif msg.message_type == MessageType.note_off:
                open_messages.pop(msg.note, None)

            quantified_messages.append(message_to_append)

        self.messages = quantified_messages
        self.sort()

    def quantise_note_lengths(self, upper_bound_multiplier, lower_bound_divisor, dotted_note_iterations=1,
                              standard_length=PPQN) -> None:
        """ Quantises the note lengths of this sequence, only affecting the ending of the notes.

        Quantises notes to the given values, ensuring that all notes are of one of the sizes defined by the
        parameters. The upper bound multiplier determines the longest possible note value, in terms of the `PPQN`. An
        upper bound of 2, e.g., would result in a maximum note length of `2 * PPQN`, meaning half-notes. The same holds
        for the lower bound, where the `PPQN` is divided by it. Furthermore, the option of having dotted notes is
        given, where each iteration adds all (possible) notes dotted up to the iteration amount, e.g., an iteration
        value of 2 would result in two-dotted notes being accepted. Note that only integer results are accepted,
        which in conjunction with the value for the `PPQN` can result in some values being rejected.

        Args:
            upper_bound_multiplier: Value by which the `PPQN` is multiplied to determine the largest note value
            lower_bound_divisor: Value by which the `PPQN` is divided to determine the smallest note value
            dotted_note_iterations: Amount of dots to allow for dotted notes
            standard_length: Note length for notes which are not closed

        """
        # Construct possible durations
        possible_durations = []
        j = upper_bound_multiplier
        while j >= 1:
            possible_durations.append(j * PPQN)
            j /= 2
        j = 2
        while j <= lower_bound_divisor:
            possible_durations.append(PPQN / j)
            j *= 2

        # Add dotted durations to array of possible durations
        dotted_durations = []
        for dotted_note_iteration in range(1, dotted_note_iterations + 1):
            for i, entry in enumerate(possible_durations):
                if i + dotted_note_iteration < len(possible_durations):
                    resulting_value = possible_durations[i]
                    for iteration in range(1, dotted_note_iteration + 1):
                        resulting_value += possible_durations[i + iteration] / 2
                    if resulting_value.is_integer():
                        dotted_durations.append(resulting_value)
        possible_durations.extend(dotted_durations)

        notes = self._get_absolute_note_array(standard_length=standard_length)

        for note in notes:
            duration = note[1].time - note[0].time
            best_fit = possible_durations[find_minimal_distance(duration, possible_durations)]
            correction = best_fit - duration
            note[1].time += correction

        self.sort()

    def merge(self, sequences: [AbsoluteSequence]) -> None:
        """ Merges this sequence with all the given ones.

        Args:
            sequences: The sequences to merge with this one

        Returns: The sequence that contains all messages of this and the given sequences, conserving the timings

        """
        for sequence in sequences:
            for msg in copy.copy(sequence.messages):
                b_insort(self.messages, msg)

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

    def diff_message_values(self) -> float:
        notes = self._get_absolute_note_array()

    def _get_absolute_note_array(self, standard_length=PPQN) -> []:
        open_messages = dict()
        notes: [[]] = []
        i = 0

        # Collect notes
        for msg in self.messages:
            # Add notes to open messages
            if msg.message_type == MessageType.note_on:
                if msg.note in open_messages:
                    logging.warning(f"Note {msg.note} at time {msg.time} not previously closed")
                    index = open_messages.pop(msg.note)
                    notes[index].append(Message(message_type=MessageType.note_off, note=msg.note, time=msg.time))

                open_messages[msg.note] = i
                notes.insert(i, [msg])
                i += 1

            # Add closing message to fitting open message
            elif msg.message_type == MessageType.note_off:
                if msg.note not in open_messages:
                    logging.warning(f"Note {msg.note} at time {msg.time} not previously opened")
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
