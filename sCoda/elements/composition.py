from __future__ import annotations

import copy
import logging
import math
import os

from sCoda.elements.message import Message, MessageType
from sCoda.sequence.sequence import Sequence
from sCoda.settings import PPQN
from sCoda.util.midi_wrapper import MidiFile
from sCoda.util.util import get_note_durations, get_tuplet_durations, get_dotted_note_durations


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
                elif msg.message_type == MessageType.key_signature:
                    if i not in meta_track_indices:
                        logging.warning("Encountered key signature change in unexpected track")

                    meta_sequence.add_absolute_message(
                        Message(message_type=MessageType.key_signature, key=msg.key, time=rounded_point_in_time))
                elif msg.message_type == MessageType.control_change:
                    meta_sequence.add_absolute_message(
                        Message(message_type=MessageType.control_change, control=msg.control, velocity=msg.velocity,
                                time=rounded_point_in_time))

        final_sequences = []

        for sequences_to_merge in sequences:
            track = copy.copy(sequences_to_merge[0])
            track.merge(sequences_to_merge[1:])
            final_sequences.append(track)

        if 0 > meta_track_index or meta_track_index >= len(final_sequences):
            raise ValueError("Invalid meta track index")

        final_sequences[meta_track_index].merge([meta_sequence])

        # TODO Testing purposes

        quantise_parameters = get_note_durations(1, 8)
        quantise_parameters += get_tuplet_durations(quantise_parameters, 3, 2)
        final_sequences[0].quantise(quantise_parameters)

        note_durations = get_note_durations(8, 8)
        triplet_durations = get_tuplet_durations(note_durations, 3, 2)
        dotted_durations = get_dotted_note_durations(note_durations, 1)

        possible_durations = note_durations + triplet_durations + dotted_durations

        final_sequences[0].quantise_note_lengths(possible_durations)

        bars = final_sequences[0].split(
            [PPQN * 4, PPQN * 4, PPQN * 4, PPQN * 4, PPQN * 4, PPQN * 4, PPQN * 4, PPQN * 4, PPQN * 4, PPQN * 4])

        print("Placeholder")

        for i, track in enumerate(bars):
            track.adjust_wait_messages()
            if i == 0:
                track.difficulty()
            # track = track.to_midi_track()
            # midi_file = MidiFile()
            # midi_file.tracks.append(track)
            # if not os.path.exists("../output"):
            #     os.makedirs("../output")
            # midi_file.save(f"../output/output{i}.mid")

        # TODO Add to composition

        return composition
