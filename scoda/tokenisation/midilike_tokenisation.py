from abc import ABC

from scoda.elements.message import Message
from scoda.exceptions.tokenisation_exception import TokenisationException
from scoda.sequences.sequence import Sequence
from scoda.tokenisation.base_tokenisation import BaseTokeniser
from scoda.utils.enumerations import Flags, MessageType


class BaseMidilikeTokeniser(BaseTokeniser, ABC):

    def __init__(self, running_time_sig: bool) -> None:
        super().__init__(running_time_sig)


class MidilikeTokeniser(BaseMidilikeTokeniser):
    """Tokeniser that uses note-like temporal representation.

    [        0] ... pad
    [        1] ... start
    [        2] ... stop
    [  3 -  26] ... wait
    [ 27 - 114] ... note on
    [115 - 202] ... note off
    [203 - 217] ... time signature numerator in eights from 2/8 to 16/8
    """

    def __init__(self, running_time_sig: bool) -> None:
        super().__init__(running_time_sig)

    def tokenise(self, sequence: Sequence, apply_buffer: bool = True, insert_border_tokens: bool = False) -> list[int]:
        tokens = []

        for message in sequence.rel.messages:
            msg_type = message.message_type

            if msg_type == MessageType.WAIT:
                self.cur_rest_buffer += message.time

                self.prv_type = MessageType.WAIT
            elif msg_type == MessageType.NOTE_ON:
                msg_note = message.note

                if not (21 <= msg_note <= 108):
                    raise TokenisationException(f"Invalid note: {msg_note}")

                tokens.extend(self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, value_shift=2))
                self.cur_rest_buffer = 0

                tokens.append(msg_note - 21 + 27)

                self.prv_type = MessageType.NOTE_ON
            elif msg_type == MessageType.NOTE_OFF:
                msg_note = message.note

                if not (21 <= msg_note <= 108):
                    raise TokenisationException(f"Invalid note: {msg_note}")

                tokens.extend(self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, value_shift=2))
                self.cur_rest_buffer = 0

                tokens.append(msg_note - 21 + 115)

                self.prv_type = MessageType.NOTE_OFF
            elif msg_type == MessageType.TIME_SIGNATURE:
                msg_numerator = message.numerator
                msg_denominator = message.denominator

                numerator = self._time_signature_to_eights(msg_numerator, msg_denominator)

                if not (self.prv_numerator == numerator and self.flags.get(Flags.RUNNING_TIME_SIG, False)):
                    tokens.extend(self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, value_shift=2))
                    self.cur_rest_buffer = 0

                    tokens.append(numerator - 2 + 203)

                self.prv_type = MessageType.TIME_SIGNATURE
                self.prv_numerator = numerator

        if apply_buffer and self.cur_rest_buffer > 0:
            tokens.extend(self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, value_shift=2))
            self.cur_rest_buffer = 0

        if insert_border_tokens:
            tokens.insert(0, 1)
            tokens.append(2)

        return tokens

    @staticmethod
    def detokenise(tokens: list[int]) -> Sequence:
        seq = Sequence()

        for token in tokens:
            if token <= 2:
                pass
            elif 3 <= token <= 26:
                seq.rel.add_message(Message(message_type=MessageType.WAIT, time=token - 2))
            elif 27 <= token <= 114:
                seq.rel.add_message(Message(message_type=MessageType.NOTE_ON, note=token - 27 + 21))
            elif 115 <= token <= 202:
                seq.rel.add_message(Message(message_type=MessageType.NOTE_OFF, note=token - 115 + 21))
            elif 203 <= token <= 217:
                seq.rel.add_message(
                    Message(message_type=MessageType.TIME_SIGNATURE, numerator=token - 203 + 2, denominator=8))

        return seq

    @staticmethod
    def get_info_notes(tokens: list[int], invalid_value: int = -1) -> list[int]:
        info = []

        for token in tokens:
            if not 27 <= token <= 114:
                info.append(invalid_value)
            else:
                info.append(token - 27 + 21)

        return info

    @staticmethod
    def get_info_circle_of_fifths(tokens: list[int], invalid_value: int = -1) -> list[int]:
        info = []

        for token in tokens:
            if not 27 <= token <= 114:
                info.append(invalid_value)
            else:
                info.append((token - 27 + 21) % 12)

        return info

    @staticmethod
    def get_info_elapsed_ticks(tokens: list[int]) -> list[int]:
        info = []
        cur_time = 0

        for token in tokens:
            info.append(cur_time)

            if 3 <= token <= 26:
                cur_time += token - 2

        return info
