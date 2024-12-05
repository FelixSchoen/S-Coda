from __future__ import annotations

import mido

from scoda.enumerations.message_type import MessageType
from scoda.midi.midi_message import MidiMessage


class MidiTrack:

    def __init__(self) -> None:
        super().__init__()
        self.name = ""
        self.messages: [MidiMessage] = []

    @staticmethod
    def parse_mido_track(mido_track) -> MidiTrack:
        track = MidiTrack()

        for msg in mido_track:
            track.messages.append(MidiMessage.parse_mido_message(msg))

        return track

    def to_mido_track(self) -> mido.MidiTrack:
        track = mido.MidiTrack()

        if self.name is not None and self.name != "":
            track.name = self.name

        time_buffer = 0

        for msg in self.messages:
            if hasattr(msg, "time") and msg.time is not None:
                time_buffer += msg.time

            if msg.message_type == MessageType.NOTE_ON:
                track.append(
                    mido.Message("note_on", note=msg.note, velocity=msg.velocity if msg.velocity is not None else 127,
                                 time=int(time_buffer)))
                time_buffer = 0
            elif msg.message_type == MessageType.NOTE_OFF:
                track.append(mido.Message("note_off", note=msg.note, velocity=0, time=int(time_buffer)))
                time_buffer = 0
            elif msg.message_type == MessageType.WAIT:
                pass
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
