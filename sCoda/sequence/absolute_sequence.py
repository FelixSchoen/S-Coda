from __future__ import annotations

import copy

from sCoda.elements.message import Message, MessageType
from sCoda.sequence.relative_sequence import RelativeSequence
from sCoda.sequence.sequence import Sequence
from sCoda.settings import PPQN
from sCoda.util.util import b_insort


class AbsoluteSequence(Sequence):
    """
    Class representing a sequence with absolute message timings.
    """

    def __init__(self) -> None:
        super().__init__()

    def add_message(self, msg: Message) -> None:
        b_insort(self.messages, msg)

    def quantise(self, fractions: [int]) -> None:
        """ Quantises the sequence to a given grid.

        Quantises the sequence stored in this object according to the given fractions. These fractions determine the
        step size of the grid, e.g., an entry of 8 would correspond in a grid size of PPQN / 8. If PPQN were 24,
        the grid would support the length 3, in this example thirty-secondth notes. If there exists a tie between two
        grid boundaries, these are first resolved by whether the quantisation would prevent a note-length of 0,
        then by the order of the fractions array. The result of this operation is that all messages of this sequence
        have a time divisible by PPQN / fraction, for all entries in fractions.

        Args:
            fractions: Array of number by which the PPQN will be divided to determine possible step-size for the grid

        """
        quantified_messages = []
        # Keep track of open messages, in order to guarantee quantisation does not smother them
        open_messages = dict()

        for msg in self.messages:
            time = msg.time
            message_to_append = copy.copy(msg)

            # Size of the steps for each of the quantisation parameters
            step_sizes = [PPQN / i for i in fractions]

            # Positions the note would land at according to each of the quantisation parameters
            positions_left = [(time // step_size) * step_size for step_size in step_sizes]
            positions_right = [positions_left[i] + step_sizes[i] for i in range(0, len(fractions))]
            positions = [positions_left, positions_right]

            # Check if exact hit exists
            if time in positions_left:
                pass
            else:
                # Entries consist of distance, index of quantisation parameter, index of position array
                distances = []
                distances_left = [(time - positions_left[i], i, 0) for i in range(0, len(fractions))]
                distances_right = [(positions_right[i] - time, i, 1) for i in range(0, len(fractions))]

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
