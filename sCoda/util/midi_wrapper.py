from __future__ import annotations

import copy

import mido

from sCoda.elements.message import MessageType, Message
from sCoda.settings import PPQN
from sCoda.util.logging import get_logger
from sCoda.util.music_theory import Key


class MidiFile:

    def __init__(self) -> None:
        super().__init__()
        self.tracks: [MidiTrack] = []
        self.PPQN = None

    def to_sequences(self, track_indices: [[int]], meta_track_indices: [int], meta_track_index: int = 0):
        from sCoda import Sequence

        logger = get_logger(__name__)

        # Create sequences to fill
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
                if msg.message_type == MessageType.note_on and any(i in indices for indices in track_indices):
                    current_sequence.add_absolute_message(
                        Message(message_type=MessageType.note_on, note=msg.note, velocity=msg.velocity,
                                time=rounded_point_in_time))
                # Note Off
                elif msg.message_type == MessageType.note_off and any(i in indices for indices in track_indices):
                    current_sequence.add_absolute_message(
                        Message(message_type=MessageType.note_off, note=msg.note, time=rounded_point_in_time))
                # Time Signature
                elif msg.message_type == MessageType.time_signature:
                    if i not in meta_track_indices:
                        logger.warning("Encountered time signature change in unexpected track.")

                    meta_sequence.add_absolute_message(
                        Message(message_type=MessageType.time_signature, numerator=msg.numerator,
                                denominator=msg.denominator, time=rounded_point_in_time))
                # Key Signature
                elif msg.message_type == MessageType.key_signature:
                    if i not in meta_track_indices:
                        logger.warning("Encountered key signature change in unexpected track.")

                    meta_sequence.add_absolute_message(
                        Message(message_type=MessageType.key_signature, key=msg.key, time=rounded_point_in_time))
                # Control change
                elif msg.message_type == MessageType.control_change:
                    meta_sequence.add_absolute_message(
                        Message(message_type=MessageType.control_change, control=msg.control, velocity=msg.velocity,
                                time=rounded_point_in_time))
                # Unknown, e.g. MetaMessage (will be ignored)
                else:
                    pass

        merged_sequences = []

        # Merge sequences according to groups
        for sequences_to_merge in sequences:
            track = copy.copy(sequences_to_merge[0])
            track.merge(sequences_to_merge[1:])
            merged_sequences.append(track)

        if 0 > meta_track_index or meta_track_index >= len(merged_sequences):
            raise ValueError("Invalid meta track index")

        merged_sequences[meta_track_index].merge([meta_sequence])

        return merged_sequences

    @staticmethod
    def open_midi_file(filename) -> MidiFile:
        midi_file = MidiFile()
        midi_file._parse_mido_file(filename)
        return midi_file

    def _parse_mido_file(self, filename):
        mido_midi_file = mido.MidiFile(filename)
        self.PPQN = mido_midi_file.ticks_per_beat

        for mido_track in mido_midi_file.tracks:
            self.tracks.append(MidiTrack.parse_mido_track(mido_track))

    def save(self, path):
        mido_midi_file = mido.MidiFile()
        mido_midi_file.ticks_per_beat = PPQN

        for track in self.tracks:
            mido_midi_file.tracks.append(track.to_mido_track())

        mido_midi_file.save(path)


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
            if msg.message_type == MessageType.note_on:
                track.append(mido.Message("note_on", note=msg.note, velocity=msg.velocity, time=int(time_buffer)))
                time_buffer = 0
            elif msg.message_type == MessageType.note_off:
                track.append(mido.Message("note_off", note=msg.note, velocity=0, time=int(time_buffer)))
                time_buffer = 0
            elif msg.message_type == MessageType.wait:
                time_buffer += msg.time
            elif msg.message_type == MessageType.time_signature:
                track.append(mido.MetaMessage("time_signature", numerator=msg.numerator, denominator=msg.denominator,
                                              time=int(time_buffer)))
                time_buffer = 0
            elif msg.message_type == MessageType.key_signature:
                track.append(mido.MetaMessage("key_signature", key=msg.key.value, time=int(time_buffer)))
                time_buffer = 0
            elif msg.message_type == MessageType.control_change:
                track.append(
                    mido.Message("control_change", channel=0, control=msg.control, value=msg.velocity,
                                 time=int(time_buffer)))
                time_buffer = 0

        return track


class MidiMessage:

    def __init__(self, message_type=None, control=None, denominator=None, numerator=None, key=None, note=None,
                 time=None,
                 velocity=None) -> None:
        super().__init__()
        self.message_type = message_type
        self.control = control
        self.denominator = denominator
        self.numerator = numerator
        self.key = key
        self.note = note
        self.time = time
        self.velocity = velocity

    @staticmethod
    def parse_mido_message(mido_message) -> MidiMessage:
        msg = MidiMessage()

        msg.time = mido_message.time

        if mido_message.type == "note_on" and mido_message.velocity > 0:
            msg.message_type = MessageType.note_on
            msg.note = mido_message.note
            msg.velocity = mido_message.velocity
        elif mido_message.type == "note_on" or mido_message.type == "note_off":
            msg.message_type = MessageType.note_off
            msg.note = mido_message.note
            msg.velocity = mido_message.velocity
        elif mido_message.type == "time_signature":
            msg.message_type = MessageType.time_signature
            msg.denominator = mido_message.denominator
            msg.numerator = mido_message.numerator
        elif mido_message.type == "key_signature":
            msg.message_type = MessageType.key_signature
            msg.key = Key(mido_message.key)
        elif mido_message.type == "control_change":
            msg.message_type = MessageType.control_change
            msg.control = mido_message.control
            msg.velocity = mido_message.value

        return msg

    @staticmethod
    def parse_internal_message(message) -> MidiMessage:
        return MidiMessage(message_type=message.message_type, time=message.time, note=message.note,
                           velocity=message.velocity, control=message.control, numerator=message.numerator,
                           denominator=message.denominator, key=message.key)
