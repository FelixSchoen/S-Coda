from __future__ import annotations

import copy
import logging

from sCoda.elements.message import Message, MessageType
from sCoda.sequence.absolute_sequence import AbsoluteSequence
from sCoda.settings import PPQN
from sCoda.util.midi_wrapper import MidiFile


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
        midi_file = MidiFile.open_midi_file(file_path)

        # Create absolute sequences
        sequences = [[AbsoluteSequence() for _ in indices] for indices in track_indices]
        meta_sequence = AbsoluteSequence()

        # PPQN scaling
        scaling_factor = PPQN / midi_file.PPQN

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

            for j, msg in enumerate(track.messages):
                # Add time induced by message
                if msg.time is not None:
                    current_point_in_time += (msg.time * scaling_factor)

                if msg.message_type == MessageType.note_on and any(i in indices for indices in track_indices):
                    current_sequence.add_message(
                        Message(message_type=MessageType.note_on, note=msg.note, velocity=msg.velocity,
                                time=current_point_in_time))
                elif msg.message_type == MessageType.note_off and any(i in indices for indices in track_indices):
                    current_sequence.add_message(
                        Message(message_type=MessageType.note_off, note=msg.note, time=current_point_in_time))
                elif msg.message_type == MessageType.time_signature:
                    if i not in meta_track_indices:
                        logging.warning("Encountered time signature change in unexpected track")

                    meta_sequence.add_message(
                        Message(message_type=MessageType.time_signature, numerator=msg.numerator,
                                denominator=msg.denominator, time=current_point_in_time))
                elif msg.message_type == MessageType.control_change:
                    meta_sequence.add_message(
                        Message(message_type=MessageType.control_change, control=msg.control, velocity=msg.velocity,
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
        final_sequences[0].quantise([2, 3, 4, 6, 8, 12])
        final_sequences[0].quantise_note_lengths(1, 2)

        split_sequences = final_sequences[0].to_relative_sequence().split([24 * 2, 24 * 2])

        for i, sequence in enumerate(split_sequences):
            sequence.transpose(5)
            sequence.adjust_wait_messages()
            track = sequence.to_midi_track()
            midi_file = MidiFile()
            midi_file.tracks.append(track)
            midi_file.save(f"../output/test{i}.mid")

        # TODO Add to composition

        return composition
