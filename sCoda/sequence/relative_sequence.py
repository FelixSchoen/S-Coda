from __future__ import annotations

import copy

from sCoda.elements.message import Message, MessageType
from sCoda.sequence.sequence import Sequence
from sCoda.util.midi_wrapper import MidiTrack, MidiMessage


class RelativeSequence(Sequence):
    """
    Class representing a sequence with relative message timings.
    """

    def __init__(self) -> None:
        super().__init__()

    def to_midi_track(self) -> MidiTrack:
        track = MidiTrack()

        for msg in self.messages:
            track.messages.append(
                MidiMessage(message_type=msg.message_type, time=msg.time, note=msg.note, velocity=msg.velocity,
                            control=msg.control, numerator=msg.numerator, denominator=msg.denominator))

        return track

    def add_message(self, msg: Message) -> None:
        self.messages.append(msg)

    def split(self, capacities: [int]) -> [RelativeSequence]:
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

    def to_absolute_sequence(self) -> Sequence:
        """ Converts this RelativeSequence to an AbsoluteSequence

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
