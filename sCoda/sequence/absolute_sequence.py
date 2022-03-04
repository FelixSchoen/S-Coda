import copy
from bisect import insort

from sCoda.elements.message import Message, MessageType
from sCoda.sequence.sequence import Sequence
from sCoda.settings import PPQN


class AbsoluteSequence(Sequence):
    """
    Class representing a sequence with absolute message timings.
    """

    def __init__(self) -> None:
        super().__init__()
        self._messages = []

    def add_message(self, msg: Message) -> None:
        insort(self._messages, (msg.time, msg))

    def quantise(self, fractions: [int]) -> None:
        """ Quantises the sequence to a given grid.

        Quantises the sequence stored in this object according to the given fractions. These fractions determine the step size
        of the grid, e.g., an entry of 8 would correspond in a grid size of PPQN / 8. If PPQN were 24, the grid would
        support the length 3, in this example thirty-secondth notes. If there exists a tie between two grid boundaries,
        these are first resolved by whether the quantisation would prevent a note-length of 0, then by the order of the
        fractions array. The result of this operation is that all messages of this sequence have a time divisible by
        PPQN / fraction, for all entries in fractions.

        Args:
            fractions: Array of number by which the PPQN will be divided to determine possible step-size for the grid

        """
        quantified_messages = []
        # Keep track of open messages, in order to guarantee quantisation does not smother them
        open_messages = dict()

        for timing, msg in self._messages:
            message_to_append = copy.deepcopy(msg)

            # Size of the steps for each of the quantisation parameters
            step_sizes = [PPQN / i for i in fractions]

            # Positions the note would land at according to each of the quantisation parameters
            positions_left = [(timing // step_size) * step_size for step_size in step_sizes]
            positions_right = [positions_left[i] + step_sizes[i] for i in range(0, len(fractions))]
            positions = [positions_left, positions_right]

            # Check if exact hit exists
            if timing in positions_left:
                pass
            else:
                # Entries consist of distance, index of quantisation parameter, index of position array
                distances = []
                distances_left = [(timing - positions_left[i], i, 0) for i in range(0, len(fractions))]
                distances_right = [(positions_right[i] - timing, i, 1) for i in range(0, len(fractions))]

                # Sort by smallest distance
                distances.extend(distances_left)
                distances.extend(distances_right)
                distances.sort()

                # Consider quantisations that could smother notes
                if msg.message_type == MessageType.note_off and msg.note in open_messages:
                    note_open_timing = open_messages[msg.note]

                    # Rank those entries back, that would induce a play time of smaller equal 0
                    for i, entry in enumerate(copy.deepcopy(distances)):
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

        self._messages = quantified_messages
