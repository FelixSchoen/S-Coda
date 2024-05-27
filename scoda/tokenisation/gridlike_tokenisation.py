import math
from abc import ABC

from scoda.elements.message import Message
from scoda.enumerations.message_type import MessageType
from scoda.enumerations.tokenisation_flags import TokenisationFlags
from scoda.exceptions.tokenisation_exception import TokenisationException
from scoda.sequences.sequence import Sequence
from scoda.tokenisation.base_tokenisation import BaseTokeniser


class BaseGridlikeTokeniser(BaseTokeniser, ABC):
    TOKEN_SEPARATOR = None

    def __init__(self, running_time_sig: bool) -> None:
        super().__init__()

        self.flags[TokenisationFlags.RUNNING_TIME_SIG] = running_time_sig


class GridlikeTokeniser(BaseGridlikeTokeniser):
    """Tokeniser that uses grid-like temporal representation. Note that input sequences are expected to represent bars,
    as the grid size definition is redone for each input sequence.

    [        0] ... pad
    [        1] ... start
    [        2] ... stop
    [        3] ... grid
    [  4 -  27] ... grid time definition
    [ 28 - 115] ... note on
    [116 - 203] ... note off
    [204 - 218] ... time signature numerator in eights from 2/8 to 16/8
    """

    def __init__(self, running_time_sig: bool) -> None:
        super().__init__(running_time_sig)

    def tokenise(self, bar_sequence: Sequence, apply_buffer: bool = True) -> list[int]:
        tokens = []
        min_grid_size = self.set_max_rest_value

        # First pass to get minimum grid size
        for message in bar_sequence.rel.messages:
            msg_type = message.message_type

            if msg_type == MessageType.WAIT:
                self.cur_rest_buffer += message.time
            elif msg_type in [MessageType.NOTE_ON, MessageType.NOTE_OFF, MessageType.TIME_SIGNATURE]:
                if self.cur_rest_buffer > 0:
                    min_grid_size = math.gcd(int(min_grid_size), int(self.cur_rest_buffer))
                self.cur_rest_buffer = 0

        # Calculate grid size for trailing waits
        if self.cur_rest_buffer > 0:
            min_grid_size = math.gcd(int(min_grid_size), int(self.cur_rest_buffer))
        self.cur_rest_buffer = 0

        # Limit grid size
        min_grid_size = min(min_grid_size, self.set_max_rest_value)

        tokens.append(min_grid_size + 3)

        # Second pass to generate tokens
        for message in bar_sequence.rel.messages:
            msg_type = message.message_type

            if msg_type == MessageType.WAIT:
                self.cur_rest_buffer += message.time

                self.prv_type = MessageType.WAIT
            elif msg_type == MessageType.NOTE_ON:
                msg_note = message.note

                if not (21 <= msg_note <= 108):
                    raise TokenisationException(f"Invalid note: {msg_note}")

                tokens.extend(self._gridlike_tokenise_flush_grid_buffer(min_grid_size=min_grid_size, wait_token=3))
                tokens.append(msg_note - 21 + 28)

                self.prv_type = MessageType.NOTE_ON
            elif msg_type == MessageType.NOTE_OFF:
                msg_note = message.note

                if not (21 <= msg_note <= 108):
                    raise TokenisationException(f"Invalid note: {msg_note}")

                tokens.extend(self._gridlike_tokenise_flush_grid_buffer(min_grid_size=min_grid_size, wait_token=3))
                tokens.append(msg_note - 21 + 116)

                self.prv_type = MessageType.NOTE_OFF
            elif msg_type == MessageType.TIME_SIGNATURE:
                msg_numerator = message.numerator
                msg_denominator = message.denominator

                numerator = self._time_signature_to_eights(msg_numerator, msg_denominator)

                if not (self.prv_numerator == numerator and self.flags.get(TokenisationFlags.RUNNING_TIME_SIG, False)):
                    tokens.extend(self._gridlike_tokenise_flush_grid_buffer(min_grid_size=min_grid_size, wait_token=3))
                    tokens.append(numerator - 2 + 204)

                self.prv_type = MessageType.TIME_SIGNATURE
                self.prv_numerator = numerator

        if apply_buffer and self.cur_rest_buffer > 0:
            tokens.extend(self._gridlike_tokenise_flush_grid_buffer(min_grid_size=min_grid_size, wait_token=3))

        return tokens

    @staticmethod
    def detokenise(tokens: list[int]) -> Sequence:
        seq = Sequence()
        prv_type = None
        min_grid_size = math.nan

        for token in tokens:
            if token <= 2:
                prv_type = "sequence_control"
            elif token == 3:
                if math.isnan(min_grid_size):
                    raise TokenisationException(f"Grid size not initialised")

                seq.add_relative_message(Message(MessageType.WAIT, time=min_grid_size))

                prv_type = MessageType.INTERNAL
            elif 4 <= token <= 27:
                if prv_type == MessageType.WAIT:
                    raise TokenisationException(f"Illegal consecutive grid size definition")

                min_grid_size = token - 3

                prv_type = MessageType.WAIT
            elif 28 <= token <= 115:
                seq.rel.add_message(Message(message_type=MessageType.NOTE_ON, note=token - 28 + 21))

                prv_type = MessageType.NOTE_ON
            elif 116 <= token <= 203:
                seq.rel.add_message(Message(message_type=MessageType.NOTE_OFF, note=token - 116 + 21))

                prv_type = MessageType.NOTE_OFF
            elif 204 <= token <= 218:
                seq.rel.add_message(
                    Message(message_type=MessageType.TIME_SIGNATURE, numerator=token - 204 + 2, denominator=8))

                prv_type = MessageType.TIME_SIGNATURE
            else:
                raise TokenisationException(f"Encountered invalid token during detokenisation: {token}")

        return seq
