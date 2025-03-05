from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import mido

from scoda.elements.message import Message
from scoda.enumerations.message_type import MessageType
from scoda.midi.midi_track import MidiTrack
from scoda.misc.scoda_logging import get_logger
from scoda.settings.settings import PPQN

if TYPE_CHECKING:
    from scoda.sequences.sequence import Sequence


class MidiFile:
    LOGGER = get_logger(__name__)

    def __init__(self) -> None:
        super().__init__()
        self.tracks: [MidiTrack] = []
        self.PPQN = PPQN

    @staticmethod
    def open(filename) -> MidiFile:
        midi_file = MidiFile()
        mido_midi_file = mido.MidiFile(filename)
        midi_file.parse_mido(mido_midi_file)
        return midi_file

    def parse_mido(self, mido_midi_file):
        self.PPQN = mido_midi_file.ticks_per_beat
        for mido_track in mido_midi_file.tracks:
            self.tracks.append(MidiTrack.parse_mido_track(mido_track))

    def convert(self, track_indices: [[int]], meta_track_indices: [int], meta_track_index: int = 0) -> list[Sequence]:
        """ Parses this `MidiFile` and returns a list of `scoda.Sequence`.

        Args:
            track_indices: A list of grouped indices of tracks. Tracks in the same group will be merged to a single
                sequence.
            meta_track_indices: A list of indices of tracks, which can contain meta messages to consider.
            meta_track_index: The index of the final sequence that should contain meta messages.

        Returns: A list of parsed sequence.

        """
        from scoda.sequences.sequence import Sequence

        # Create sequence to fill
        sequences = [[Sequence() for _ in indices] for indices in track_indices]
        meta_sequence = Sequence()

        # PPQN scaling
        scaling_factor = PPQN / self.PPQN

        default_channel = None

        # Iterate over all tracks contained in this file
        for i, track in enumerate(self.tracks):
            # Skip tracks not specified
            if not any(i in indices for indices in track_indices) and i not in meta_track_indices:
                continue

            # Keep track of current point in time
            current_point_in_time = 0

            # Get current sequence
            current_sequence = None
            if any(i in indices for indices in track_indices):
                group_indices = next(array for array in track_indices if i in array)
                current_sequence = sequences[track_indices.index(group_indices)][group_indices.index(i)]
            elif i in meta_track_indices:
                current_sequence = meta_sequence

            # Parse messages
            for j, msg in enumerate(track.messages):
                if default_channel is None and msg.channel is not None:
                    default_channel = msg.channel

                # Add time induced by message
                current_point_in_time += (msg.time * scaling_factor)
                rounded_point_in_time = round(current_point_in_time)

                # Note On
                if msg.message_type == MessageType.NOTE_ON and any(i in indices for indices in track_indices):
                    current_sequence.add_absolute_message(
                        Message(message_type=MessageType.NOTE_ON, channel=msg.channel, note=msg.note,
                                velocity=msg.velocity, time=rounded_point_in_time))
                # Note Off
                elif msg.message_type == MessageType.NOTE_OFF and any(i in indices for indices in track_indices):
                    current_sequence.add_absolute_message(
                        Message(message_type=MessageType.NOTE_OFF, channel=msg.channel, note=msg.note,
                                time=rounded_point_in_time))
                # Time Signature
                elif msg.message_type == MessageType.TIME_SIGNATURE:
                    if i not in meta_track_indices:
                        MidiFile.LOGGER.debug("MidiFile: Encountered time signature change in unexpected track.")

                    meta_sequence.add_absolute_message(
                        Message(message_type=MessageType.TIME_SIGNATURE, channel=msg.channel, numerator=msg.numerator,
                                denominator=msg.denominator, time=rounded_point_in_time))
                # Key Signature
                elif msg.message_type == MessageType.KEY_SIGNATURE:
                    if i not in meta_track_indices:
                        MidiFile.LOGGER.debug("MidiFile: Encountered key signature change in unexpected track.")

                    meta_sequence.add_absolute_message(
                        Message(message_type=MessageType.KEY_SIGNATURE, channel=msg.channel, key=msg.key,
                                time=rounded_point_in_time))
                # Control change
                elif msg.message_type == MessageType.CONTROL_CHANGE:
                    meta_sequence.add_absolute_message(
                        Message(message_type=MessageType.CONTROL_CHANGE, channel=msg.channel, velocity=msg.velocity,
                                control=msg.control, time=rounded_point_in_time))
                # Program change
                elif msg.message_type == MessageType.PROGRAM_CHANGE:
                    current_sequence.add_absolute_message(
                        Message(message_type=MessageType.PROGRAM_CHANGE, channel=msg.channel, program=msg.program,
                                time=rounded_point_in_time))
                # Unknown, e.g. MetaMessage (will be ignored)
                else:
                    pass

        merged_sequences = []

        # Merge sequence according to groups
        for sequences_to_merge in sequences:
            for seq in sequences_to_merge:
                seq.normalise()
            track = copy.copy(sequences_to_merge[0])
            track.merge(sequences_to_merge[1:])
            merged_sequences.append(track)

        if 0 > meta_track_index or meta_track_index >= len(merged_sequences):
            raise ValueError("Invalid meta track index")

        meta_track = merged_sequences[meta_track_index]
        meta_track.merge([meta_sequence])

        # Set standard time if not set
        if not any(timing_tuple[0] == 0 for timing_tuple in
                   meta_track.get_message_times_of_type([MessageType.TIME_SIGNATURE])):
            meta_track.add_absolute_message(
                Message(message_type=MessageType.TIME_SIGNATURE, channel=default_channel, numerator=4, denominator=4,
                        time=0))

        return merged_sequences

    def save(self, path):
        mido_midi_file = mido.MidiFile()
        mido_midi_file.ticks_per_beat = PPQN

        for track in self.tracks:
            mido_midi_file.tracks.append(track.to_mido_track())

        mido_midi_file.save(path)
