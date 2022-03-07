from __future__ import annotations

import copy
import logging

from sCoda.elements.message import Message, MessageType
from sCoda.sequence.sequence import Sequence
from sCoda.settings import PPQN
from sCoda.util.util import b_insort, find_minimal_distance


class AbsoluteSequence(Sequence):
    """
    Class representing a sequence with absolute message timings.
    """

    def __init__(self) -> None:
        super().__init__()

    def sort(self) -> None:
        self.messages.sort(key=lambda x: x.time)

    def add_message(self, msg: Message) -> None:
        b_insort(self.messages, msg)

    def quantise(self, divisors: [int]) -> None:
        """ Quantises the sequence to a given grid.

        Quantises the sequence stored in this object according to the given fractions. These fractions determine the
        step size of the grid, e.g., an entry of 8 would correspond in a grid size of PPQN / 8. If PPQN were 24,
        the grid would support the length 3, in this example thirty-secondth notes. If there exists a tie between two
        grid boundaries, these are first resolved by whether the quantisation would prevent a note-length of 0,
        then by the order of the fractions array. The result of this operation is that all messages of this sequence
        have a time divisible by PPQN / fraction, for all entries in fractions.

        Args:
            divisors: Array of number by which the PPQN will be divided to determine possible step-size for the grid

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
            positions = [positions_left, positions_right]

            # Check if exact hit exists
            if time in positions_left:
                pass
            else:
                # Entries consist of distance, index of quantisation parameter, index of position array
                distances = []
                distances_left = [(time - positions_left[i], i, 0) for i in range(0, len(divisors))]
                distances_right = [(positions_right[i] - time, i, 1) for i in range(0, len(divisors))]

                # Sort by smallest distance
                distances.extend(distances_left)
                distances.extend(distances_right)
                distances.sort()

                # Consider quantisations that could smother notes
                if msg.message_type == MessageType.note_off and msg.note in open_messages:
                    note_open_timing = open_messages[msg.note]

                    # Rank those entries back, that would induce a play time of smaller equal 0
                    for i, entry in enumerate(copy.copy(distances)):
                        if positions[entry[2]][entry[1]] - note_open_timing <= 0:
                            distances.append(distances.pop(i))

                # Change timing of message to append
                message_to_append.time = positions[distances[0][2]][distances[0][1]]

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
        open_messages = dict()

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

        # Keep track of notes, insert start and corresponding stop message
        notes = []
        i = 0

        for msg in self.messages:
            # Add notes to open messages
            if msg.message_type == MessageType.note_on:
                if msg.note in open_messages:
                    logging.warning("Note not previously closed")
                    index = open_messages[msg.note]
                    notes[index].append(Message(message_type=MessageType.note_off, note=msg.note, time=msg.time))

                open_messages[msg.note] = i
                notes.insert(i, [msg])
                i += 1

            # Add closing message to fitting open message
            elif msg.message_type == MessageType.note_off:
                if msg.note not in open_messages:
                    logging.warning("Note not previously opened")
                index = open_messages[msg.note]
                notes[index].append(msg)

        # Close still open messages with standard length
        for key, value in open_messages.items():
            logging.warning(f"Did not close message {key}")
            msg = notes[value][0]
            notes[value].append(
                Message(message_type=MessageType.note_off, note=msg.note, time=msg.time + standard_length))

        for note in notes:
            duration = note[1].time - note[0].time
            best_fit = possible_durations[find_minimal_distance(duration, possible_durations)]

            # print(f"Note {note[0].note} duration {duration} best fit {best_fit}")

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

    def to_relative_sequence(self) -> Sequence:
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
