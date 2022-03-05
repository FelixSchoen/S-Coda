from __future__ import annotations

import copy
import logging

from mido import MidiFile

from sCoda.elements.message import Message, MessageType
from sCoda.sequence.absolute_sequence import AbsoluteSequence
from sCoda.settings import PPQN


class Composition:
    """
    Class representing a composition that contains (multiple) tracks.
    """

    def __init__(self) -> None:
        super().__init__()
        self._tracks = []

    @staticmethod
    def from_file(file_path: str, track_indices: [[int]],
                  meta_track_indices: [int], meta_track_index: int = 0) -> Composition:
        composition = Composition()
        midi_file = MidiFile(file_path)

        # Create absolute sequences
        sequences = [[AbsoluteSequence() for _ in indices] for indices in track_indices]
        meta_sequence = AbsoluteSequence()

        # PPQN scaling
        scaling_factor = PPQN / midi_file.ticks_per_beat

        # Iterate over all tracks in midi file
        for i, track in enumerate(midi_file.tracks):
            # Skip tracks not specified
            if not any(i in indices for indices in track_indices) and i not in meta_track_indices:
                continue

            # Keep track of current point in time
            current_point_in_time = 0

            # Get current sequence
            current_sequence = None
            if any(i in indices for indices in track_indices):
                array = next(array for array in track_indices if i in array)
                current_sequence = sequences[track_indices.index(array)][array.index(i)]
            elif i in meta_track_indices:
                current_sequence = meta_sequence

            for j, msg in enumerate(track):
                # Add time induced by message
                if msg.time is not None:
                    current_point_in_time += (msg.time * scaling_factor)

                if msg.type == "note_on" and msg.velocity > 0:
                    current_sequence.add_message(
                        Message(message_type=MessageType.note_on, note=msg.note, velocity=msg.velocity,
                                time=current_point_in_time))
                elif msg.type == "note_on" and msg.velocity == 0:
                    current_sequence.add_message(
                        Message(message_type=MessageType.note_off, note=msg.note, time=current_point_in_time))
                elif msg.type == "time_signature":
                    if i not in meta_track_indices:
                        logging.warning("Encountered time signature change in unexpected track")

                    meta_sequence.add_message(
                        Message(message_type=MessageType.time_signature, numerator=msg.numerator,
                                denominator=msg.denominator, time=current_point_in_time))
                elif msg.type == "control_change":
                    meta_sequence.add_message(
                        Message(message_type=MessageType.control_change, control=msg.control, velocity=msg.value,
                                time=current_point_in_time))

        final_sequences = []

        for sequences_to_merge in sequences:
            sequence = copy.copy(sequences_to_merge[0])
            sequence.merge(sequences_to_merge[1:])
            final_sequences.append(sequence)

        if 0 > meta_track_index or meta_track_index >= len(final_sequences):
            raise ValueError("Invalid meta track index")

        final_sequences[meta_track_index].merge([meta_sequence])

        # TODO Testing purposes
        final_sequences[0].quantise([8, 12])
        split_sequences = final_sequences[0].to_relative_sequence().split([24*4])
        print(f"Length of sequences: {len(split_sequences)}, starting to print now:")

        for msg in split_sequences[0].messages:
            print(msg)

        # TODO Add to composition

        return composition
