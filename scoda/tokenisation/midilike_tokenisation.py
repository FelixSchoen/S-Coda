from abc import ABC

from scoda.elements.message import Message
from scoda.enumerations.message_type import MessageType
from scoda.enumerations.tokenisation_flags import TokenisationFlags
from scoda.exceptions.tokenisation_exception import TokenisationException
from scoda.misc.music_theory import CircleOfFifths
from scoda.sequences.sequence import Sequence
from scoda.tokenisation.base_tokenisation import BaseTokeniser


class BaseMidilikeTokeniser(BaseTokeniser, ABC):

    def __init__(self, running_time_sig: bool) -> None:
        super().__init__()

        self.flags[TokenisationFlags.RUNNING_TIME_SIG] = running_time_sig


class StandardMidilikeTokeniser(BaseMidilikeTokeniser):
    """Tokeniser that uses midi-like temporal representation.

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

    def tokenise(self, sequence: Sequence, apply_buffer: bool = True) -> list[int]:
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

                tokens.extend(self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, index_time_def=4))
                self.cur_rest_buffer = 0

                tokens.append(msg_note - 21 + 28)

                self.prv_type = MessageType.NOTE_ON
            elif msg_type == MessageType.NOTE_OFF:
                msg_note = message.note

                if not (21 <= msg_note <= 108):
                    raise TokenisationException(f"Invalid note: {msg_note}")

                tokens.extend(self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, index_time_def=4))
                self.cur_rest_buffer = 0

                tokens.append(msg_note - 21 + 116)

                self.prv_type = MessageType.NOTE_OFF
            elif msg_type == MessageType.TIME_SIGNATURE:
                msg_numerator = message.numerator
                msg_denominator = message.denominator

                numerator = self._time_signature_to_eights(msg_numerator, msg_denominator)

                if not (self.prv_numerator == numerator and self.flags.get(TokenisationFlags.RUNNING_TIME_SIG, False)):
                    tokens.extend(self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, index_time_def=4))
                    self.cur_rest_buffer = 0

                    tokens.append(numerator - 2 + 204)

                self.prv_type = MessageType.TIME_SIGNATURE
                self.prv_numerator = numerator

        if apply_buffer and self.cur_rest_buffer > 0:
            tokens.extend(self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, index_time_def=4))
            self.cur_rest_buffer = 0

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
            else:
                raise TokenisationException(f"Encountered invalid token during detokenisation: {token}")

        return seq


class CoFMidilikeTokeniser(BaseMidilikeTokeniser):
    """Tokeniser that uses midi-like temporal representation and circle of fifths distances.

    [        0] ... pad
    [        1] ... start
    [        2] ... stop
    [        3] ... bar separator
    [  4 -  27] ... wait
    [ 28 -  44] ... octave shift between notes
    [ 45 -  56] ... note on without octave in distance on the circle of fifths
    [ 57 -  68] ... note off without octave in distance on the circle of fifths
    [ 69 -  84] ... time signature numerator in eights from 2/8 to 16/8
    """

    def __init__(self, running_octave: bool, running_time_sig: bool) -> None:
        super().__init__(running_time_sig)

        self.flags[TokenisationFlags.RUNNING_OCTAVE] = running_octave

        self.prv_octave = None

    def reset_previous(self) -> None:
        super().reset_previous()

        # A4 as base note
        self.prv_note = 69
        self.prv_octave = 4

    def tokenise(self, sequence: Sequence, apply_buffer: bool = True) -> list[int]:
        tokens = []

        for message in sequence.rel.messages:
            msg_type = message.message_type

            if msg_type == MessageType.WAIT:
                self.cur_rest_buffer += message.time

                self.prv_type = MessageType.WAIT
            elif msg_type == MessageType.NOTE_ON or msg_type == MessageType.NOTE_OFF:
                msg_note = message.note

                if not (21 <= msg_note <= 108):
                    raise TokenisationException(f"Invalid note: {msg_note}")

                # Get distances
                octave_tgt = msg_note // 12 - 1
                octave_src = self.prv_note // 12 - 1
                octave_shift = octave_tgt - octave_src
                assert -8 <= octave_shift <= 8

                cof_dist = CircleOfFifths.get_distance(self.prv_note, msg_note)
                assert -5 <= cof_dist <= 6

                tokens.extend(self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, index_time_def=4))
                self.cur_rest_buffer = 0

                # Insert octave shift (if necessary) and note distance
                if not (self.prv_octave == octave_tgt and self.flags.get(TokenisationFlags.RUNNING_OCTAVE, False)):
                    tokens.append((octave_shift + 8) + 28)
                shifter_on_off = 45 if msg_type == MessageType.NOTE_ON else 57
                tokens.append((cof_dist + 5) + shifter_on_off)

                self.prv_type = msg_type
                self.prv_note = msg_note
                self.prv_octave = octave_tgt
            elif msg_type == MessageType.TIME_SIGNATURE:
                msg_numerator = message.numerator
                msg_denominator = message.denominator

                numerator = self._time_signature_to_eights(msg_numerator, msg_denominator)

                if not (self.prv_numerator == numerator and self.flags.get(TokenisationFlags.RUNNING_TIME_SIG, False)):
                    tokens.extend(self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, index_time_def=4))
                    self.cur_rest_buffer = 0

                    tokens.append(numerator - 2 + 69)

                self.prv_type = MessageType.TIME_SIGNATURE
                self.prv_numerator = numerator

        if apply_buffer and self.cur_rest_buffer > 0:
            tokens.extend(self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, index_time_def=4))
            self.cur_rest_buffer = 0

        return tokens

    @staticmethod
    def detokenise(tokens: list[int]) -> Sequence:
        seq = Sequence()
        prv_note = 69  # A4 is base note
        prv_octave = 4

        for token in tokens:
            if token <= 3:
                pass
            elif 4 <= token <= 27:
                seq.rel.add_message(Message(message_type=MessageType.WAIT, time=token - 3))
            elif 28 <= token <= 44:
                prv_octave += token - 28 - 8
            elif 45 <= token <= 68:
                note_base = CircleOfFifths.from_distance(prv_note, (token - 45) - 5)
                note = note_base + prv_octave * 12 + 12  # Shifts notes to A0

                prv_note = note

                if 45 <= token <= 56:
                    seq.rel.add_message(Message(message_type=MessageType.NOTE_ON, note=note))
                else:
                    seq.rel.add_message(Message(message_type=MessageType.NOTE_OFF, note=note))
            elif 69 <= token <= 84:
                seq.rel.add_message(
                    Message(message_type=MessageType.TIME_SIGNATURE, numerator=token - 69 + 2, denominator=8))
            else:
                raise TokenisationException(f"Encountered invalid token during detokenisation: {token}")

        return seq
