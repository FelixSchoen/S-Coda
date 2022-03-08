from __future__ import annotations

import copy
import logging
from typing import TYPE_CHECKING

from sCoda.elements.message import Message, MessageType
from sCoda.sequence.abstract_sequence import AbstractSequence
from sCoda.settings import NOTE_LOWER_BOUND, NOTE_UPPER_BOUND, PPQN
from sCoda.util.midi_wrapper import MidiTrack, MidiMessage

if TYPE_CHECKING:
    from sCoda.sequence.absolute_sequence import AbsoluteSequence


class RelativeSequence(AbstractSequence):
    """ Class representing a sequence with relative message timings.

    """

    def __init__(self) -> None:
        super().__init__()

    def to_midi_track(self) -> MidiTrack:
        """ Converts the sequence to a `MidiTrack`

        Returns: The corresponding `MidiTrack`

        """
        track = MidiTrack()

        for msg in self.messages:
            track.messages.append(
                MidiMessage(message_type=msg.message_type, time=msg.time, note=msg.note, velocity=msg.velocity,
                            control=msg.control, numerator=msg.numerator, denominator=msg.denominator))

        return track

    def add_message(self, msg: Message) -> None:
        self.messages.append(msg)

    def split(self, capacities: [int]) -> [RelativeSequence]:
        """ Splits the sequence into parts of the given capacity.

        Creates up to `len(capacities) + 1` new `RelativeSequence`s, where the first `len(capacities)` entries contain
        sequences of the given capacities, while the last one contains any remaining notes. Messages at the boundaries
        of a capacity are split up and possible reinserted at the beginning of the next sequence.

        Args:
            capacities: An array of capacities to split the sequence into

        Returns: An array of `RelativeSequence`s of the desired size

        """
        split_sequences = []
        working_memory = copy.copy(self.messages)

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
                    if len(current_sequence.messages) > 0:
                        split_sequences.append(current_sequence)
                        current_sequence = next_sequence
                    break

                # Retrieve next message
                msg = working_memory.pop(0)

                # Check messages, if capacity 0 add to next sequence for most of them
                if msg.message_type == MessageType.note_on:
                    if remaining_capacity > 0:
                        current_sequence.add_message(msg)
                        open_messages[msg.note] = copy.copy(msg)
                    else:
                        next_sequence_queue.append(msg)
                # For stop messages, add them to the current sequence
                elif msg.message_type == MessageType.note_off:
                    current_sequence.add_message(msg)
                    open_messages.pop(msg.note, None)
                elif msg.message_type == MessageType.time_signature or msg.message_type == MessageType.control_change:
                    if remaining_capacity > 0:
                        current_sequence.add_message(msg)
                    else:
                        next_sequence_queue.append(msg)
                elif msg.message_type == MessageType.wait:
                    # Can add message in entirety
                    if msg.time <= remaining_capacity:
                        remaining_capacity -= msg.time
                        current_sequence.add_message(msg)
                    # Have to split message
                    else:
                        carry_time = msg.time - remaining_capacity

                        if remaining_capacity > 0:
                            current_sequence.add_message(
                                Message(message_type=MessageType.wait, time=remaining_capacity))

                        for key, value in open_messages.items():
                            current_sequence.add_message(Message(message_type=MessageType.note_off, note=value.note))
                            next_sequence_queue.append(
                                Message(message_type=MessageType.note_on, note=value.note, velocity=value.velocity))

                        next_sequence_queue.append(Message(message_type=MessageType.wait, time=carry_time))

                        split_sequences.append(current_sequence)
                        working_memory[0:0] = next_sequence_queue
                        current_sequence = next_sequence
                        break

        # Check if still capacity left
        if len(working_memory) > 0:
            current_sequence.messages.extend(working_memory)

        # Add current sequence if it is not empty
        if len(current_sequence.messages) > 0:
            split_sequences.append(current_sequence)

        return split_sequences

    def consolidate(self, sequence: RelativeSequence) -> None:
        """ Consolidates the two sequences, resulting in the current sequence containing messages from both of the
        previous sequences.

        Args:
            sequence: A sequence which should be appended to this sequence

        """
        self.messages.extend(sequence.messages)

    def transpose(self, transpose_by: int) -> None:
        """ Transposes the sequence by the given amount.

        If the lower or upper bound is undercut over exceeded, these notes are transposed by an octave each.

        Args:
            transpose_by: Half-tone steps to transpose by

        """
        for msg in self.messages:
            if msg.message_type == MessageType.note_on or msg.message_type == MessageType.note_off:
                msg.note += transpose_by
                while msg.note < NOTE_LOWER_BOUND:
                    msg.note += 12
                while msg.note > NOTE_UPPER_BOUND:
                    msg.note -= 12

    def adjust_wait_messages(self) -> None:
        """ Consolidates and then splits up wait messages to a maximum size of `PPQN`.

        """
        open_messages = dict()
        messages_normalized = []
        messages_buffer = []
        wait_buffer = 0

        for msg in self.messages:
            if msg.message_type == MessageType.wait:
                if len(messages_buffer) > 0:
                    messages_normalized.extend(messages_buffer)
                    messages_buffer = []
                wait_buffer += msg.time
            else:
                # Split up wait messages to maximum length of PPQN
                while wait_buffer > PPQN:
                    messages_normalized.append(Message(message_type=MessageType.wait, time=PPQN))
                    wait_buffer -= PPQN
                if wait_buffer > 0:
                    messages_normalized.append(Message(message_type=MessageType.wait, time=wait_buffer))

                # Keep track of open notes
                if msg.message_type == MessageType.note_on:
                    open_messages[msg.note] = True
                elif msg.message_type == MessageType.note_off:
                    open_messages.pop(msg.note, None)

                messages_buffer.append(msg)
                wait_buffer = 0

        if len(messages_buffer) > 0:
            messages_normalized.extend(messages_buffer)

        if len(open_messages) > 0:
            logging.warning("The sequence contains messages that have not been closed")
        self.messages = messages_normalized

    def to_absolute_sequence(self) -> AbsoluteSequence:
        """ Converts this `RelativeSequence` to an `AbsoluteSequence`

        Returns: The absolute representation of this sequence

        """
        from sCoda.sequence.absolute_sequence import AbsoluteSequence
        absolute_sequence = AbsoluteSequence()
        current_point_in_time = 0

        for msg in self.messages:
            if msg.message_type == MessageType.wait:
                current_point_in_time += msg.time
            else:
                message_to_add = copy.copy(msg)
                message_to_add.time = current_point_in_time
                absolute_sequence.add_message(message_to_add)

        return absolute_sequence
