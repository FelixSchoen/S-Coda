from __future__ import annotations

from sCoda.elements.message import Message, MessageType
from sCoda.sequence.sequence import Sequence
from sCoda.util.hn_iterator import HNIterator
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
        iterator = HNIterator(iter(enumerate(self.messages)))

        current_sequence = RelativeSequence()
        next_sequence = RelativeSequence()
        open_notes = dict()

        # Try to split current sequence at given point
        for capacity in capacities:
            next_sequence_queue = []
            remaining_capacity = capacity

            while remaining_capacity >= 0:
                # Check if end-of-sequence was reached prematurely
                if not iterator.has_next():
                    if len(current_sequence.messages) > 0:
                        split_sequences.append(current_sequence)
                    break

                # Retrieve next message
                _, msg = iterator.next()

                # Check messages, if capacity 0 add to next sequence for most of them
                if msg.message_type == MessageType.note_on:
                    if remaining_capacity > 0:
                        current_sequence.add_message(msg)
                        open_notes[msg.note] = True
                    else:
                        next_sequence_queue.append(msg)
                # For stop messages, add them to the current sequence
                elif msg.message_type == MessageType.note_off:
                    current_sequence.add_message(msg)
                    open_notes.pop(msg.note, None)
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
                        # TODO Close open messages and open again at the start of the next
                        fit_time = msg.time - remaining_capacity
                        carry_time = msg.time - fit_time

                        current_sequence.add_message(Message(message_type=MessageType.wait, time=fit_time))
                        next_sequence_queue.append(Message(message_type=MessageType.wait, time=carry_time))

                        split_sequences.append(current_sequence)
                        next_sequence.messages.extend(next_sequence_queue)
                        current_sequence = next_sequence
                        break

        # TODO Redundant line
        current_sequence = next_sequence

        # Check if still capacity left
        if iterator.has_next():
            i, _ = iterator.peek()
            current_sequence.messages.extend(self.messages[i:-1])

        # Add current sequence if it is not empty
        if len(current_sequence.messages) > 0:
            split_sequences.append(current_sequence)

        return split_sequences
