from __future__ import annotations

from scoda.elements.message import Message
from scoda.enumerations.message_type import MessageType
from scoda.misc.music_theory import MusicMapping


class MidiMessage:

    def __init__(self, message_type=None, channel=None, control=None, denominator=None, numerator=None, key=None,
                 note=None, time=None, velocity=None, program=None) -> None:
        super().__init__()
        self.message_type = message_type
        self.channel = channel
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

        if hasattr(mido_message, "channel"):
            msg.channel = mido_message.channel

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
        return MidiMessage(message_type=message.message_type, channel=message.channel, time=message.time,
                           note=message.note, velocity=message.velocity, control=message.control,
                           numerator=message.numerator, denominator=message.denominator, key=message.key,
                           program=message.program)

    def __str__(self) -> str:
        return f"MidiMessage(type={self.message_type}, channel={self.channel}, time={self.time}, note={self.note})"
