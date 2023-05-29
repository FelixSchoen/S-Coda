import math
from abc import ABC, abstractmethod

from scoda.elements.message import Message
from scoda.exceptions.tokenisation_exception import TokenisationException
from scoda.sequences.sequence import Sequence
from scoda.settings.settings import PPQN
from scoda.utils.enumerations import MessageType, Flags


class Tokeniser(ABC):

    def __init__(self, running_time_sig: bool) -> None:
        super().__init__()

        self.flags = dict()
        self.flags[Flags.RUNNING_TIME_SIG] = running_time_sig

        self.cur_time = None
        self.cur_time_target = None
        self.cur_rest_buffer = None

        self.prv_type = None
        self.prv_value = None
        self.prv_numerator = None

        """The maximum value up to which consecutive rests will be consolidated"""
        self.set_max_rest_value = PPQN

        self.reset()

    def reset(self) -> None:
        self.reset_time()
        self.reset_previous()

    def reset_time(self) -> None:
        self.cur_time = 0
        self.cur_time_target = 0
        self.cur_rest_buffer = 0

    def reset_previous(self) -> None:
        self.prv_type = None
        self.prv_value = -1
        self.prv_numerator = -1

    def _general_tokenise_flush_time_buffer(self, time: int, value_shift: int) -> list[int]:
        tokens = []

        while time > self.set_max_rest_value:
            tokens.append(self.set_max_rest_value + value_shift)
            time -= self.set_max_rest_value

        if time > 0:
            tokens.append(time + value_shift)

        return tokens

    def _notelike_tokenise_flush_rest_buffer(self, apply_target: bool, wait_token: int, value_shift: int) -> list[int]:
        tokens = []

        # Insert rests of length up to `set_max_rest_value`
        while self.cur_rest_buffer > self.set_max_rest_value:
            if not (self.prv_value == self.set_max_rest_value and self.flags.get(Flags.RUNNING_VALUE, False)):
                tokens.append(int(self.set_max_rest_value + value_shift))
                self.prv_value = self.set_max_rest_value

            tokens.append(wait_token)
            self.cur_time += self.set_max_rest_value
            self.cur_rest_buffer -= self.set_max_rest_value

        # Insert rests smaller than `set_max_rest_value`
        if self.cur_rest_buffer > 0:
            if not (self.prv_value == self.cur_rest_buffer and self.flags.get(Flags.RUNNING_VALUE, False)):
                tokens.append(int(self.cur_rest_buffer + value_shift))
                self.prv_value = self.cur_rest_buffer
            tokens.append(wait_token)

        self.cur_time += self.cur_rest_buffer
        self.cur_rest_buffer = 0

        # If there are open notes, extend the sequence to the minimum needed time target
        if apply_target and self.cur_time_target > self.cur_time:
            self.cur_rest_buffer += self.cur_time_target - self.cur_time
            tokens.extend(
                self._notelike_tokenise_flush_rest_buffer(apply_target=False, wait_token=wait_token,
                                                          value_shift=value_shift))

        return tokens

    def _gridlike_tokenise_flush_grid_buffer(self, min_grid_size: int, wait_token: int) -> list[int]:
        tokens = []

        while self.cur_rest_buffer > 0:
            tokens.append(wait_token)
            self.cur_rest_buffer -= min_grid_size

        return tokens

    @abstractmethod
    def tokenise(self, sequence: Sequence) -> list[int]:
        pass

    @staticmethod
    @abstractmethod
    def detokenise(tokens: list[int]) -> Sequence:
        pass

    @staticmethod
    def _time_signature_to_eights(numerator: int, denominator: int) -> int:
        scaled = numerator * (8 / denominator)

        if (not float(scaled).is_integer()):
            raise TokenisationException(
                f"Original time signature of {int(numerator)}/{int(denominator)} cannot be represented as multiples of eights")

        if not 2 <= scaled <= 16:
            raise TokenisationException(
                f"Invalid time signature numerator: {int(numerator)}")

        return int(scaled)


class NotelikeTokeniser(Tokeniser):
    """Tokeniser that uses note-like temporal representation.

    [        0] ... pad
    [        1] ... start
    [        2] ... stop
    [        3] ... wait
    [  4 -  27] ... value definition
    [ 28 - 115] ... note
    [116 - 130] ... time signature numerator in eights from 2/8 to 16/8
    """

    def __init__(self, running_value: bool, running_time_sig: bool) -> None:
        super().__init__(running_time_sig)

        self.flags[Flags.RUNNING_VALUE] = running_value

    def tokenise(self, sequence: Sequence, apply_buffer: bool = True, reset_time: bool = True) -> list[int]:
        tokens = []
        event_pairings = sequence.abs.absolute_note_array(include_meta_messages=True)

        for event_pairing in event_pairings:
            msg_type = event_pairing[0].message_type
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
                        self._notelike_tokenise_flush_rest_buffer(apply_target=False, wait_token=3, value_shift=3))

                # Check if value of note has to be defined
                if not (self.prv_value == msg_value and self.flags.get(Flags.RUNNING_VALUE, False)):
                    tokens.extend(self._general_tokenise_flush_time_buffer(msg_value, value_shift=3))

                tokens.append(msg_note - 21 + 28)

                self.cur_time_target = max(self.cur_time_target, self.cur_time + msg_value)
                self.prv_type = MessageType.NOTE_ON
                self.prv_value = msg_value
            elif msg_type == MessageType.TIME_SIGNATURE:
                msg_numerator = event_pairing[0].numerator
                msg_denominator = event_pairing[0].denominator

                numerator = self._time_signature_to_eights(msg_numerator, msg_denominator)

                # Check if time signature has to be defined
                if not (self.prv_numerator == numerator and self.flags.get(Flags.RUNNING_TIME_SIG, False)):
                    self.cur_rest_buffer += msg_time - self.cur_time
                    tokens.extend(
                        self._notelike_tokenise_flush_rest_buffer(apply_target=False, wait_token=3, value_shift=3))
                    tokens.append(numerator - 2 + 116)

                self.prv_type = MessageType.TIME_SIGNATURE
                self.prv_numerator = numerator
            elif msg_type == MessageType.INTERNAL:
                self.cur_rest_buffer += msg_time - self.cur_time
                self.prv_type = MessageType.INTERNAL

        if apply_buffer:
            tokens.extend(
                self._notelike_tokenise_flush_rest_buffer(apply_target=True, wait_token=3, value_shift=3))

        if reset_time:
            self.reset_time()

        return tokens

    @staticmethod
    def detokenise(tokens: list[int]) -> Sequence:
        seq = Sequence()
        cur_time = 0
        prv_type = None
        prv_value = math.nan

        for token in tokens:
            if token <= 2:
                prv_type = "sequence_control"
            elif token == 3:
                cur_time += prv_value
                prv_type = MessageType.WAIT
            elif 4 <= token <= 27:
                if prv_type == MessageType.INTERNAL:
                    prv_value += token - 3
                else:
                    prv_value = token - 3
                prv_type = MessageType.INTERNAL
            elif 28 <= token <= 115:
                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_ON, note=token - 28 + 21, time=cur_time))
                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_OFF, note=token - 28 + 21,
                            time=cur_time + prv_value))
                prv_type = MessageType.NOTE_ON
            elif 116 <= token <= 130:
                seq.add_absolute_message(
                    Message(message_type=MessageType.TIME_SIGNATURE, time=cur_time,
                            numerator=token - 116 + 2, denominator=8)
                )
                prv_type = MessageType.TIME_SIGNATURE
            else:
                raise TokenisationException(f"Encountered invalid token during detokenisation: {token}")

        return seq


class MIDIlikeTokeniser(Tokeniser):
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


class GridlikeTokeniser(Tokeniser):
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

    def tokenise(self, bar_seq: Sequence, apply_buffer: bool = True) -> list[int]:
        tokens = []
        min_grid_size = self.set_max_rest_value

        # First pass to get minimum grid size
        for message in bar_seq.rel.messages:
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
        for message in bar_seq.rel.messages:
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

                if not (self.prv_numerator == numerator and self.flags.get(Flags.RUNNING_TIME_SIG, False)):
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
                if min_grid_size == -1:
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

        return seq


class TransposedNotelikeTokeniser(Tokeniser):
    """Tokeniser that uses transposed temporal representation with a note-like approach, i.e., all occurrences of a note
    are shown first before any other note is handled. Note that input sequences are required to represent bars, as the
    transposed representation is done on a per-bar basis.

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

        self.flags[Flags.RUNNING_VALUE] = running_value

    def tokenise(self, bar_seq: Sequence, apply_buffer: bool = True, reset_time: bool = True) -> list[int]:
        tokens = []
        event_pairings = bar_seq.abs.absolute_note_array(include_meta_messages=True)

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
                            self._notelike_tokenise_flush_rest_buffer(apply_target=False, wait_token=4, value_shift=5))

                    # Check if value of note has to be defined
                    if not (self.prv_value == msg_value and self.flags.get(Flags.RUNNING_VALUE, False)):
                        tokens.extend(self._general_tokenise_flush_time_buffer(msg_value, value_shift=5))

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
                    if not (self.prv_numerator == numerator and self.flags.get(Flags.RUNNING_TIME_SIG, False)):
                        self.cur_rest_buffer += msg_time - self.cur_time
                        tokens.extend(
                            self._notelike_tokenise_flush_rest_buffer(apply_target=False, wait_token=4, value_shift=5))
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
                self._notelike_tokenise_flush_rest_buffer(apply_target=True, wait_token=4, value_shift=5))

        if reset_time:
            self.reset_time()

        # Insert bar border mark
        tokens.append(5)

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
