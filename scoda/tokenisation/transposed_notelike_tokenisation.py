import math
from abc import ABC

from scoda.elements.message import Message
from scoda.enumerations.message_type import MessageType
from scoda.enumerations.tokenisation_flags import TokenisationFlags
from scoda.exceptions.tokenisation_exception import TokenisationException
from scoda.sequences.sequence import Sequence
from scoda.settings.settings import PPQN
from scoda.tokenisation.base_tokenisation import BaseTokeniser


class BaseTransposedNotelikeTokeniser(BaseTokeniser, ABC):

    def __init__(self, running_time_sig: bool) -> None:
        super().__init__()

        self.flags[TokenisationFlags.RUNNING_TIME_SIG] = running_time_sig


# TODO
class TransposedNotelikeTokeniser(BaseTransposedNotelikeTokeniser):
    """Tokeniser that uses transposed temporal representation with a note-like approach, i.e., all occurrences of a note
    are shown first before any other note is handled. Note that input sequences are expected to represent bars,
    as the transposed representation is done on a per-bar basis.

    [        0] ... pad
    [        1] ... start
    [        2] ... stop
    [        3] ... play
    [        4] ... wait
    [        5] ... bar border
    [  6 -  29] ... value definition
    [ 30 - 117] ... note
    [118 - 132] ... time signature numerator in eights from 2/8 to 16/8
    """

    def __init__(self, running_value: bool, running_time_sig: bool) -> None:
        super().__init__(running_time_sig)

        self.flags[TokenisationFlags.RUNNING_VALUE] = running_value

    def tokenise(self, bar_sequence: Sequence, apply_buffer: bool = True, reset_time: bool = True,
                 insert_border_tokens: bool = False) -> list[int]:
        tokens = []
        event_pairings = bar_sequence.abs.get_message_time_pairings(
            [MessageType.NOTE_ON, MessageType.NOTE_OFF, MessageType.TIME_SIGNATURE, MessageType.INTERNAL])

        event_pairings_by_note = dict()

        # Entries consist of (message type, hashable)
        ordered_type_value_pairs = list()

        for event_pairing in event_pairings:
            message = event_pairing[0]

            if message.message_type == MessageType.NOTE_ON:
                if not any(x[1] == message.note for x in ordered_type_value_pairs):
                    ordered_type_value_pairs.append((MessageType.NOTE_ON, message.note))

                event_pairings_by_note.setdefault(message.note, list())
                event_pairings_by_note[message.note].append(event_pairing)
            elif message.message_type == MessageType.TIME_SIGNATURE:
                if any(x[1] == MessageType.TIME_SIGNATURE for x in ordered_type_value_pairs):
                    raise TokenisationException("Bar contains more than one time signature")

                ordered_type_value_pairs.insert(0, (MessageType.TIME_SIGNATURE, MessageType.TIME_SIGNATURE))

                event_pairings_by_note.setdefault(MessageType.TIME_SIGNATURE, list())
                event_pairings_by_note[MessageType.TIME_SIGNATURE].append(event_pairing)
            elif message.message_type == MessageType.INTERNAL:
                if any(x[1] == MessageType.INTERNAL for x in ordered_type_value_pairs):
                    raise TokenisationException("Bar contains more than one internal message")

                ordered_type_value_pairs.append((MessageType.INTERNAL, MessageType.INTERNAL))

                event_pairings_by_note.setdefault(MessageType.INTERNAL, list())
                event_pairings_by_note[MessageType.INTERNAL].append(event_pairing)

        for ordered_type_value_pair in ordered_type_value_pairs:
            msg_type = ordered_type_value_pair[0]
            event_pairings_for_key = event_pairings_by_note[ordered_type_value_pair[1]]

            # Define note
            if msg_type == MessageType.NOTE_ON:
                msg_note = event_pairings_for_key[0][0].note
                if not (21 <= msg_note <= 108):
                    raise TokenisationException(f"Invalid note: {msg_note}")

                tokens.append(msg_note - 21 + 30)

            for event_pairing in event_pairings_for_key:
                msg_time = event_pairing[0].time

                if msg_type == MessageType.NOTE_ON:
                    msg_note = event_pairing[0].note
                    msg_value = event_pairing[1].time - msg_time

                    if not (21 <= msg_note <= 108):
                        raise TokenisationException(f"Invalid note: {msg_note}")

                    # Check if message occurs at current time, if not place rest messages
                    if not self.cur_time == msg_time:
                        self.cur_rest_buffer += msg_time - self.cur_time
                        tokens.extend(
                            self._notelike_tokenise_flush_rest_buffer(apply_target=False, wait_token=4,
                                                                      index_time_def=6))

                    # Check if value of note has to be defined
                    if not (self.prv_value == msg_value and self.flags.get(TokenisationFlags.RUNNING_VALUE, False)):
                        tokens.extend(self._general_tokenise_flush_time_buffer(msg_value, index_time_def=6))

                    # Play note
                    tokens.append(3)

                    self.cur_time_target = max(self.cur_time_target, self.cur_time + msg_value)
                    self.prv_type = MessageType.NOTE_ON
                    self.prv_value = msg_value
                elif msg_type == MessageType.TIME_SIGNATURE:
                    msg_numerator = event_pairing[0].numerator
                    msg_denominator = event_pairing[0].denominator

                    numerator = self._time_signature_to_eights(msg_numerator, msg_denominator)

                    # Check if time signature has to be defined
                    if not (self.prv_numerator == numerator and self.flags.get(TokenisationFlags.RUNNING_TIME_SIG,
                                                                               False)):
                        self.cur_rest_buffer += msg_time - self.cur_time
                        tokens.extend(
                            self._notelike_tokenise_flush_rest_buffer(apply_target=False, wait_token=4,
                                                                      index_time_def=6))
                        tokens.append(numerator - 2 + 118)

                    self.prv_type = MessageType.TIME_SIGNATURE
                    self.prv_numerator = numerator
                elif msg_type == MessageType.INTERNAL:
                    self.cur_rest_buffer += msg_time - self.cur_time
                    self.prv_type = MessageType.INTERNAL

            # Reset time to beginning of bar
            self.cur_time = 0

        if apply_buffer:
            tokens.extend(
                self._notelike_tokenise_flush_rest_buffer(apply_target=True, wait_token=4, index_time_def=6))

        if reset_time:
            self.reset_time()

        # Insert bar border mark
        tokens.append(5)

        if insert_border_tokens:
            tokens.insert(0, 1)
            tokens.append(2)

        return tokens

    @staticmethod
    def detokenise(tokens: list[int]) -> Sequence:
        seq = Sequence()
        time_bar_start = 0

        cur_time_bar = 0

        prv_type = None
        prv_note = math.nan
        prv_value = math.nan
        prv_numerator = math.nan

        for token in tokens:
            if token <= 2:
                prv_type = "sequence_control"
            elif token == 3:
                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_ON, note=prv_note,
                            time=time_bar_start + cur_time_bar))
                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_OFF, note=prv_note,
                            time=time_bar_start + cur_time_bar + prv_value))

                prv_type = MessageType.NOTE_ON
            elif token == 4:
                cur_time_bar += prv_value

                prv_type = MessageType.WAIT
            elif token == 5:
                time_bar_start += prv_numerator * PPQN / 2
                cur_time_bar = 0

                prv_type = "bar_border"
            elif 6 <= token <= 29:
                if prv_type == "value_definition":
                    prv_value += token - 5
                else:
                    prv_value = token - 5

                prv_type = "value_definition"
            elif 30 <= token <= 117:
                cur_time_bar = 0

                prv_note = token - 30 + 21
                prv_type = "note_definition"
            elif 118 <= token <= 132:
                numerator = token - 118 + 2

                seq.add_absolute_message(
                    Message(message_type=MessageType.TIME_SIGNATURE, time=time_bar_start + cur_time_bar,
                            numerator=numerator, denominator=8)
                )

                prv_type = MessageType.TIME_SIGNATURE
                prv_numerator = numerator
            else:
                raise TokenisationException(f"Encountered invalid token during detokenisation: {token}")

        return seq
