from abc import ABC

from scoda.elements.message import Message
from scoda.exceptions.tokenisation_exception import TokenisationException
from scoda.misc.enumerations import Flags, MessageType
from scoda.sequences.sequence import Sequence
from scoda.tokenisation.base_tokenisation import BaseTokeniser


class BaseMidilikeTokeniser(BaseTokeniser, ABC):

    def __init__(self, running_time_sig: bool) -> None:
        super().__init__(running_time_sig)


class MidilikeTokeniser(BaseMidilikeTokeniser):
    """Tokeniser that uses note-like temporal representation.

    [        0] ... pad
    [        1] ... start
    [        2] ... stop
    [        3] ... bar separator
    [  4 -  27] ... wait
    [ 28 - 115] ... note on
    [116 - 203] ... note off
    [204 - 218] ... time signature numerator in eights from 2/8 to 16/8
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

                tokens.extend(self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, value_shift=3))
                self.cur_rest_buffer = 0

                tokens.append(msg_note - 21 + 28)

                self.prv_type = MessageType.NOTE_ON
            elif msg_type == MessageType.NOTE_OFF:
                msg_note = message.note

                if not (21 <= msg_note <= 108):
                    raise TokenisationException(f"Invalid note: {msg_note}")

                tokens.extend(self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, value_shift=3))
                self.cur_rest_buffer = 0

                tokens.append(msg_note - 21 + 116)

                self.prv_type = MessageType.NOTE_OFF
            elif msg_type == MessageType.TIME_SIGNATURE:
                msg_numerator = message.numerator
                msg_denominator = message.denominator

                numerator = self._time_signature_to_eights(msg_numerator, msg_denominator)

                if not (self.prv_numerator == numerator and self.flags.get(Flags.RUNNING_TIME_SIG, False)):
                    tokens.extend(self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, value_shift=3))
                    self.cur_rest_buffer = 0

                    tokens.append(numerator - 2 + 204)

                self.prv_type = MessageType.TIME_SIGNATURE
                self.prv_numerator = numerator

        if apply_buffer and self.cur_rest_buffer > 0:
            tokens.extend(self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, value_shift=3))
            self.cur_rest_buffer = 0

        if insert_border_tokens:
            tokens.insert(0, 1)
            tokens.append(2)

        return tokens

    @staticmethod
    def detokenise(tokens: list[int]) -> Sequence:
        seq = Sequence()

        for token in tokens:
            if token <= 3:
                pass
            elif 4 <= token <= 27:
                seq.rel.add_message(Message(message_type=MessageType.WAIT, time=token - 3))
            elif 28 <= token <= 115:
                seq.rel.add_message(Message(message_type=MessageType.NOTE_ON, note=token - 28 + 21))
            elif 116 <= token <= 203:
                seq.rel.add_message(Message(message_type=MessageType.NOTE_OFF, note=token - 116 + 21))
            elif 204 <= token <= 218:
                seq.rel.add_message(
                    Message(message_type=MessageType.TIME_SIGNATURE, numerator=token - 204 + 2, denominator=8))

        return seq

    @staticmethod
    def get_info_notes(tokens: list[int], invalid_value: int = -1) -> list[int]:
        info = []

        for token in tokens:
            if not 28 <= token <= 115:
                info.append(invalid_value)
            else:
                info.append(token - 28 + 21)

        return info

    @staticmethod
    def get_info_circle_of_fifths(tokens: list[int], invalid_value: int = -1) -> list[int]:
        info = []

        for token in tokens:
            if not 28 <= token <= 115:
                info.append(invalid_value)
            else:
                info.append((token - 28 + 21) % 12)

        return info

    @staticmethod
    def get_info_elapsed_ticks(tokens: list[int]) -> list[int]:
        info = []
        cur_time = 0

        for token in tokens:
            info.append(cur_time)

            if 4 <= token <= 27:
                cur_time += token - 3

        return info
