from __future__ import annotations

import copy
import logging
import math

from sCoda.elements.message import Message, MessageType
from sCoda.sequence.sequence import Sequence
from sCoda.settings import PPQN
from sCoda.util.midi_wrapper import MidiFile


class Composition:
    """ Class representing a composition that contains (multiple) tracks.

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
        sequences = [[Sequence() for _ in indices] for indices in track_indices]
        meta_sequence = Sequence()

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
                current_point_in_time += (msg.time * scaling_factor)
                rounded_point_in_time = round(current_point_in_time)

                if msg.message_type == MessageType.note_on and any(i in indices for indices in track_indices):
                    current_sequence.add_absolute_message(
                        Message(message_type=MessageType.note_on, note=msg.note, velocity=msg.velocity,
                                time=rounded_point_in_time))
                elif msg.message_type == MessageType.note_off and any(i in indices for indices in track_indices):
                    current_sequence.add_absolute_message(
                        Message(message_type=MessageType.note_off, note=msg.note, time=rounded_point_in_time))
                elif msg.message_type == MessageType.time_signature:
                    if i not in meta_track_indices:
                        logging.warning("Encountered time signature change in unexpected track")

                    meta_sequence.add_absolute_message(
                        Message(message_type=MessageType.time_signature, numerator=msg.numerator,
                                denominator=msg.denominator, time=rounded_point_in_time))
                elif msg.message_type == MessageType.control_change:
                    meta_sequence.add_absolute_message(
                        Message(message_type=MessageType.control_change, control=msg.control, velocity=msg.velocity,
                                time=rounded_point_in_time))

        final_sequences = []

        for sequences_to_merge in sequences:
            sequence = copy.copy(sequences_to_merge[0])
            sequence.merge(sequences_to_merge[1:])
            final_sequences.append(sequence)

        if 0 > meta_track_index or meta_track_index >= len(final_sequences):
            raise ValueError("Invalid meta track index")

        final_sequences[meta_track_index].merge([meta_sequence])

        # TODO Testing purposes
        # final_sequences[0]._get_abs()._get_absolute_note_array()

        quantise_parameters = [2 ** 3, 2 ** 3 + 2 ** 2]
        quantise_parameters = [2 ** 2, 2 ** 2 + 2 ** 1]
        final_sequences[0].quantise(quantise_parameters)
        final_sequences[0].quantise_note_lengths(8, 8)

        # for msg in final_sequences[0]._get_abs().messages:
        #     print(msg)

        split_sequences = final_sequences[0].split([math.inf])

        for i, sequence in enumerate(split_sequences):
            sequence.adjust_wait_messages()
            track = sequence.to_midi_track()
            midi_file = MidiFile()
            midi_file.tracks.append(track)
            midi_file.save(f"../output/test{i}.mid")

        # TODO Add to composition

        return composition
