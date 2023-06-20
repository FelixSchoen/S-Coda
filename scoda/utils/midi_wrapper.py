from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import mido

from scoda.elements.message import Message
from scoda.settings.settings import PPQN
from scoda.utils.enumerations import MessageType
from scoda.utils.music_theory import MusicMapping
from scoda.utils.scoda_logging import setup_logger

if TYPE_CHECKING:
    from scoda.sequences.sequence import Sequence


class MidiFile:
    LOGGER = setup_logger(__name__)

    def __init__(self) -> None:
        super().__init__()
        self.tracks: [MidiTrack] = []
        self.PPQN = PPQN

    @staticmethod
    def open_midi_file(filename) -> MidiFile:
        midi_file = MidiFile()
        mido_midi_file = mido.MidiFile(filename)
        midi_file.parse_mido_file(mido_midi_file)
        return midi_file

    def parse_mido_file(self, mido_midi_file):
        self.PPQN = mido_midi_file.ticks_per_beat
        for mido_track in mido_midi_file.tracks:
            self.tracks.append(MidiTrack.parse_mido_track(mido_track))

    def save(self, path):
        mido_midi_file = mido.MidiFile()
        mido_midi_file.ticks_per_beat = PPQN

        for track in self.tracks:
            mido_midi_file.tracks.append(track.to_mido_track())

        mido_midi_file.save(path)

    def to_sequences(self, track_indices: [[int]], meta_track_indices: [int], meta_track_index: int = 0) -> list[
        Sequence]:
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
                # Add time induced by message
                current_point_in_time += (msg.time * scaling_factor)
                rounded_point_in_time = round(current_point_in_time)

                # Note On
                if msg.message_type == MessageType.NOTE_ON and any(i in indices for indices in track_indices):
                    current_sequence.add_absolute_message(
                        Message(message_type=MessageType.NOTE_ON, note=msg.note, velocity=msg.velocity,
                                time=rounded_point_in_time))
                # Note Off
                elif msg.message_type == MessageType.NOTE_OFF and any(i in indices for indices in track_indices):
                    current_sequence.add_absolute_message(
                        Message(message_type=MessageType.NOTE_OFF, note=msg.note, time=rounded_point_in_time))
                # Time Signature
                elif msg.message_type == MessageType.TIME_SIGNATURE:
                    if i not in meta_track_indices:
                        MidiFile.LOGGER.warning("Encountered time signature change in unexpected track.")

                    meta_sequence.add_absolute_message(
                        Message(message_type=MessageType.TIME_SIGNATURE, numerator=msg.numerator,
                                denominator=msg.denominator, time=rounded_point_in_time))
                # Key Signature
                elif msg.message_type == MessageType.KEY_SIGNATURE:
                    if i not in meta_track_indices:
                        MidiFile.LOGGER.warning("Encountered key signature change in unexpected track.")

                    meta_sequence.add_absolute_message(
                        Message(message_type=MessageType.KEY_SIGNATURE, key=msg.key, time=rounded_point_in_time))
                # Control change
                elif msg.message_type == MessageType.CONTROL_CHANGE:
                    meta_sequence.add_absolute_message(
                        Message(message_type=MessageType.CONTROL_CHANGE, velocity=msg.velocity, control=msg.control,
                                time=rounded_point_in_time))
                # Program change
                elif msg.message_type == MessageType.PROGRAM_CHANGE:
                    current_sequence.add_absolute_message(
                        Message(message_type=MessageType.PROGRAM_CHANGE, program=msg.program,
                                time=rounded_point_in_time))
                # Unknown, e.g. MetaMessage (will be ignored)
                else:
                    pass

        merged_sequences = []

        # Merge sequence according to groups
        for sequences_to_merge in sequences:
            #
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
                   meta_track.get_message_timings_of_type([MessageType.TIME_SIGNATURE])):
            meta_track.add_absolute_message(
                Message(message_type=MessageType.TIME_SIGNATURE, numerator=4, denominator=4, time=0))

        return merged_sequences


class MidiTrack:

    def __init__(self) -> None:
        super().__init__()
        self.messages: [MidiMessage] = []

    @staticmethod
    def parse_mido_track(mido_track) -> MidiTrack:
        track = MidiTrack()

        for msg in mido_track:
            track.messages.append(MidiMessage.parse_mido_message(msg))

        return track

    def to_mido_track(self) -> mido.MidiTrack:
        track = mido.MidiTrack()
        time_buffer = 0

        for msg in self.messages:
            if msg.message_type == MessageType.NOTE_ON:
                track.append(
                    mido.Message("note_on", note=msg.note, velocity=msg.velocity if msg.velocity is not None else 127,
                                 time=int(time_buffer)))
                time_buffer = 0
            elif msg.message_type == MessageType.NOTE_OFF:
                track.append(mido.Message("note_off", note=msg.note, velocity=0, time=int(time_buffer)))
                time_buffer = 0
            elif msg.message_type == MessageType.WAIT:
                time_buffer += msg.time
            elif msg.message_type == MessageType.TIME_SIGNATURE:
                track.append(mido.MetaMessage("time_signature", numerator=msg.numerator, denominator=msg.denominator,
                                              time=int(time_buffer)))
                time_buffer = 0
            elif msg.message_type == MessageType.KEY_SIGNATURE:
                track.append(mido.MetaMessage("key_signature", key=msg.key.value, time=int(time_buffer)))
                time_buffer = 0
            elif msg.message_type == MessageType.CONTROL_CHANGE:
                track.append(
                    mido.Message("control_change", channel=0, control=msg.control, value=msg.velocity,
                                 time=int(time_buffer)))
                time_buffer = 0

        return track


class MidiMessage:

    def __init__(self, message_type=None, control=None, denominator=None, numerator=None, key=None, note=None,
                 time=None, velocity=None, program=None) -> None:
        super().__init__()
        self.message_type = message_type
        self.control = control
        self.denominator = denominator
        self.numerator = numerator
        self.key = key
        self.note = note
        self.time = time
        self.velocity = velocity
        self.program = program

    @staticmethod
    def parse_mido_message(mido_message) -> MidiMessage:
        msg = MidiMessage()

        msg.time = mido_message.time

        if mido_message.type == "note_on" and mido_message.velocity > 0:
            msg.message_type = MessageType.NOTE_ON
            msg.note = mido_message.note
            msg.velocity = mido_message.velocity
        elif (mido_message.type == "note_on" and mido_message.velocity == 0) or mido_message.type == "note_off":
            msg.message_type = MessageType.NOTE_OFF
            msg.note = mido_message.note
            msg.velocity = mido_message.velocity
        elif mido_message.type == "time_signature":
            msg.message_type = MessageType.TIME_SIGNATURE
            msg.denominator = mido_message.denominator
            msg.numerator = mido_message.numerator
        elif mido_message.type == "key_signature":
            msg.message_type = MessageType.KEY_SIGNATURE
            msg.key = MusicMapping.KeyKeyMapping[mido_message.key]
        elif mido_message.type == "control_change":
            msg.message_type = MessageType.CONTROL_CHANGE
            msg.control = mido_message.control
            msg.velocity = mido_message.value
        elif mido_message.type == "program_change":
            msg.message_type = MessageType.PROGRAM_CHANGE
            msg.program = mido_message.program

        return msg

    @staticmethod
    def parse_internal_message(message: Message) -> MidiMessage:
        return MidiMessage(message_type=message.message_type, time=message.time, note=message.note,
                           velocity=message.velocity, control=message.control, numerator=message.numerator,
                           denominator=message.denominator, key=message.key, program=message.program)

    def __str__(self) -> str:
        return f"MidiMessage(type={self.message_type}, time={self.time}, note={self.note})"
