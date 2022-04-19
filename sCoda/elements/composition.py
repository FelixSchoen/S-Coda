from __future__ import annotations

import copy
import logging

from sCoda.elements.bar import Bar
from sCoda.elements.message import Message, MessageType
from sCoda.elements.track import Track
from sCoda.sequence.sequence import Sequence
from sCoda.settings import PPQN
from sCoda.util.midi_wrapper import MidiFile
from sCoda.util.music_theory import Key
from sCoda.util.util import get_note_durations, get_tuplet_durations


class Composition:
    """ Class representing a composition that contains (multiple) tracks.

    """

    def __init__(self, tracks: [Track]) -> None:
        super().__init__()
        self._tracks = tracks

    @property
    def tracks(self) -> [Track]:
        return self._tracks

    @staticmethod
    def from_file(file_path: str, track_indices: [[int]],
                  meta_track_indices: [int], meta_track_index: int = 0) -> Composition:
        """ Creates a new composition from the given MIDI file.

        Args: file_path: Path to the MIDI file track_indices: Array of arrays of track indices, indices in the same
        sub-array will be merged to a single track meta_track_indices: Indices of tracks to consider for meta
        messages meta_track_index: Which final track to merge the meta messages into

        Returns: The created composition

        """
        # Open file
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

        extracted_sequences = []

        for sequences_to_merge in sequences:
            track = copy.copy(sequences_to_merge[0])
            track.merge(sequences_to_merge[1:])
            extracted_sequences.append(track)

        if 0 > meta_track_index or meta_track_index >= len(extracted_sequences):
            raise ValueError("Invalid meta track index")

        extracted_sequences[meta_track_index].merge([meta_sequence])

        # Construct quantisation parameters
        quantise_parameters = get_note_durations(1, 8)
        quantise_parameters += get_tuplet_durations(quantise_parameters, 3, 2)

        # Quantisation
        for sequence in extracted_sequences:
            sequence.quantise(quantise_parameters)
            sequence.quantise_note_lengths()

        # Start splitting into bars
        meta_track = extracted_sequences[meta_track_index]
        time_signature_timings = meta_track.get_timing_of_message_type(MessageType.time_signature)
        key_signature_timings = meta_track.get_timing_of_message_type(MessageType.key_signature)

        # Create copies of sequences in order to split into bars
        # TODO Check if works without copy
        modifiable_sequences = [modifiable_sequence for modifiable_sequence in extracted_sequences]
        bars = [[] for _ in extracted_sequences]

        if len(time_signature_timings) == 0:
            time_signature_timings = [0]

        # Split into bars, carry key and time signature
        current_point_in_time = 0
        current_ts_numerator = 4
        current_ts_denominator = 4
        current_key = None

        # Create list of bars of equal lengths
        tracks_synchronised = False
        while not tracks_synchronised:
            # Obtain new time or key signatures
            time_signature = next((timing for timing in time_signature_timings if timing[0] <= current_point_in_time)
                                  , None)
            key_signature = next((timing for timing in key_signature_timings if timing[0] <= current_point_in_time)
                                 , None)

            # Remove time signature from list, change has occurred
            if time_signature is not None:
                time_signature_timings.pop(0)
                current_ts_numerator = time_signature[1].numerator
                current_ts_denominator = time_signature[1].denominator

            # Remove key signature from list, change has occurred
            if key_signature is not None:
                key_signature_timings.pop(0)
                current_key = key_signature[1].key

            # Calculate length of current bar based on time signature
            length_bar = PPQN * (current_ts_numerator / (current_ts_denominator / 4))
            current_point_in_time += length_bar

            # Split sequences into bars
            tracks_synchronised = True
            for i, sequence in enumerate(modifiable_sequences):
                split_up = sequence.split([length_bar])

                # Check if we reached the end of the sequence
                if len(split_up) > 1:
                    tracks_synchronised = False
                    modifiable_sequences[i] = split_up[1]
                # Fill with placeholder empty sequence
                else:
                    if len(split_up) == 0:
                        split_up.append(Sequence())
                    modifiable_sequences[i] = Sequence()

                # Append split bar to list of bars
                bars[i].append(Bar(split_up[0], current_ts_numerator, current_ts_denominator, Key(current_key)))

        # Quantise note lengths again, in case splitting into bars affected them
        for bars_track in bars:
            for bar in bars_track:
                bar._sequence.quantise_note_lengths()

        # Create tracks from bars
        tracks = []
        for track_index in range(0, len(bars)):
            track = Track(bars[track_index])
            tracks.append(track)

        # Create composition from tracks
        composition = Composition(tracks)
        return composition
