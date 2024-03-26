import math
from abc import ABC

from scoda.elements.message import Message
from scoda.exceptions.tokenisation_exception import TokenisationException
from scoda.sequences.sequence import Sequence
from scoda.settings.settings import PPQN
from scoda.tokenisation.base_tokenisation import BaseTokeniser
from scoda.utils.enumerations import Flags, MessageType
from scoda.utils.music_theory import CircleOfFifths


class BaseNotelikeTokeniser(BaseTokeniser, ABC):

    def __init__(self, running_value: bool, running_time_sig: bool) -> None:
        super().__init__(running_time_sig)

        self.flags[Flags.RUNNING_VALUE] = running_value


class StandardNotelikeTokeniser(BaseNotelikeTokeniser):
    """Tokeniser that uses note-like temporal representation.

    [        0] ... pad
    [        1] ... start
    [        2] ... stop
    [        3] ... wait
    [        4] ... bar seperator
    [  5 -  28] ... value definition
    [ 29 - 116] ... note
    [117 - 131] ... time signature numerator in eights from 2/8 to 16/8
    [      132] ... note with previous pitch (running pitch only)
    """

    def __init__(self, running_value: bool, running_pitch: bool, running_time_sig: bool) -> None:
        super().__init__(running_value, running_time_sig)

        self.flags[Flags.RUNNING_PITCH] = running_pitch

    def tokenise(self, sequence: Sequence, apply_buffer: bool = True, reset_time: bool = True,
                 insert_border_tokens: bool = False) -> list[int]:
        tokens = []
        event_pairings = sequence.abs.get_message_time_pairings(
            [MessageType.NOTE_ON, MessageType.NOTE_OFF, MessageType.TIME_SIGNATURE, MessageType.INTERNAL])

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
                        self._notelike_tokenise_flush_rest_buffer(apply_target=False, wait_token=3, value_shift=4))

                # Check if value of note has to be defined
                if not (self.prv_value == msg_value and self.flags.get(Flags.RUNNING_VALUE, False)):
                    tokens.extend(self._general_tokenise_flush_time_buffer(msg_value, value_shift=4))

                # Check if pitch of note has to be defined
                if not (self.prv_note == msg_note and self.flags.get(Flags.RUNNING_PITCH, False)):
                    tokens.append(msg_note - 21 + 29)
                else:
                    tokens.append(132)

                self.cur_time_target = max(self.cur_time_target, self.cur_time + msg_value)
                self.prv_type = MessageType.NOTE_ON
                self.prv_note = msg_note
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
                    tokens.append(numerator - 2 + 117)

                self.prv_type = MessageType.TIME_SIGNATURE
                self.prv_numerator = numerator
            elif msg_type == MessageType.INTERNAL:
                self.cur_rest_buffer += msg_time - self.cur_time
                self.prv_type = MessageType.INTERNAL

        if apply_buffer:
            tokens.extend(
                self._notelike_tokenise_flush_rest_buffer(apply_target=True, wait_token=3, value_shift=4))

        if reset_time:
            self.reset_time()

        if insert_border_tokens:
            tokens.insert(0, 1)
            tokens.append(2)

        return tokens

    @staticmethod
    def detokenise(tokens: list[int]) -> Sequence:
        seq = Sequence()
        cur_time = 0
        prv_type = None
        prv_note = None
        prv_value = math.nan

        for token in tokens:
            if token <= 2:
                prv_type = "sequence_control"
            elif token == 3:
                cur_time += prv_value
                prv_type = MessageType.WAIT
            elif token == 4:
                prv_type = "sequence_control"
            elif 5 <= token <= 28:
                if prv_type == MessageType.INTERNAL:
                    prv_value += token - 4
                else:
                    prv_value = token - 4
                prv_type = MessageType.INTERNAL
            elif 29 <= token <= 116:
                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_ON, note=token - 29 + 21, time=cur_time))
                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_OFF, note=token - 29 + 21,
                            time=cur_time + prv_value))
                prv_type = MessageType.NOTE_ON
                prv_note = token - 29 + 21
            elif 117 <= token <= 131:
                seq.add_absolute_message(
                    Message(message_type=MessageType.TIME_SIGNATURE, time=cur_time,
                            numerator=token - 117 + 2, denominator=8)
                )
                prv_type = MessageType.TIME_SIGNATURE
            elif token == 132:
                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_ON, note=prv_note, time=cur_time))
                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_OFF, note=prv_note, time=cur_time + prv_value))
                prv_type = MessageType.NOTE_ON
            else:
                raise TokenisationException(f"Encountered invalid token during detokenisation: {token}")

        return seq

    @staticmethod
    def get_info_notes(tokens: list[int], invalid_value: int = -1) -> list[int]:
        info = []
        prv_note = None

        for token in tokens:
            if token == 132:
                info.append(prv_note)
            elif not 29 <= token <= 116:
                info.append(invalid_value)
            else:
                info.append(token - 29 + 21)
                prv_note = token - 29 + 21

        return info

    @staticmethod
    def get_info_circle_of_fifths(tokens: list[int], invalid_value: int = -1) -> list[int]:
        info = []
        prv_note = None

        for token in tokens:
            if token == 132:
                info.append(prv_note % 12)
            elif not 29 <= token <= 116:
                info.append(invalid_value)
            else:
                info.append((token - 29 + 21) % 12)
                prv_note = token - 29 + 21

        return info

    @staticmethod
    def get_info_elapsed_ticks(tokens: list[int]) -> list[int]:
        info = []
        cur_time = 0
        prv_type = None
        prv_value = math.nan

        for token in tokens:
            info.append(cur_time)

            if token == 3:
                cur_time += prv_value
                prv_type = MessageType.WAIT
            elif 5 <= token <= 28:
                if prv_type == MessageType.INTERNAL:
                    prv_value += token - 4
                else:
                    prv_value = token - 4
                prv_type = MessageType.INTERNAL
            else:
                prv_type = "general_message"

        return info

    @staticmethod
    def get_valid_tokens(tokens: list[int], min_bars: int = -1, bar_limit_hard: bool = False,
                         previous_state: dict = None, running_value: bool = False, running_pitch: bool = False,
                         running_time_sig: bool = False) -> (list[int], dict[str, int]):
        """

        Args:
            tokens: Tokens to create valid messages for
            min_bars: Minimum amount of bars to generate
            bar_limit_hard: If the minimum amount is also an exact amount
            previous_state: The previous allowed messages for performance reasons
            running_value: If running values are allowed
            running_pitch: If running pitches are allowed
            running_time_sig: If running time signatures are allowed

        Returns: A list of valid tokens and the current state

        """
        # TODO Check everything before actual implementation
        # TODO Implement running values
        # TODO Implement bar seperator
        cur_bar_index = 0
        cur_bar_capacity = 4 * PPQN
        cur_time = 0
        cur_bar_time = 0
        prv_type = None
        prv_note = None
        prv_value = math.nan
        seq_started = 1 in tokens
        seq_stopped = 2 in tokens

        if previous_state is not None:
            cur_bar_index = previous_state["cur_bar_index"]
            cur_bar_capacity = previous_state["cur_bar_capacity"]
            cur_time = previous_state["cur_time"]
            cur_bar_time = previous_state["cur_bar_time"]
            prv_type = previous_state["prv_type"]
            prv_value = previous_state["prv_value"]
            seq_started |= previous_state["seq_started"]
            seq_stopped |= previous_state["seq_stopped"]

        for token in tokens:
            if token <= 2:
                prv_type = "sequence_control"
            elif token == 3:
                cur_time += prv_value
                cur_bar_time += prv_value

                while cur_bar_time > cur_bar_capacity:
                    cur_bar_time -= cur_bar_capacity
                    cur_bar_index += 1

                prv_type = MessageType.WAIT
            elif token == 4:
                prv_type = "sequence_control"
            elif 5 <= token <= 28:
                if prv_type == MessageType.INTERNAL:
                    prv_value += token - 4
                else:
                    prv_value = token - 4
                prv_type = MessageType.INTERNAL
            elif 29 <= token <= 116:
                prv_type = MessageType.NOTE_ON
                prv_note = token - 29 + 21
            elif 117 <= token <= 131:
                cur_bar_capacity = int(((token - 117 + 2) / 8) * PPQN)
                prv_type = MessageType.TIME_SIGNATURE
            elif token == 132:
                prv_type = MessageType.NOTE_ON
            else:
                raise TokenisationException(f"Encountered invalid token during validity check: {token}")

        valid_tokens = []

        # padding TODO
        if seq_started and seq_stopped:
            valid_tokens.append(0)
        # start
        if not seq_started:
            valid_tokens.append(1)
        # stop
        if seq_started and not seq_stopped and (min_bars == -1 or cur_bar_index == min_bars - 1):
            valid_tokens.append(2)
        # wait
        if seq_started and not seq_stopped \
                and (not bar_limit_hard
                     or cur_bar_time + prv_value <= cur_bar_capacity
                     or cur_bar_index + 1 + (
                             prv_value - (cur_bar_capacity - cur_bar_time)) // cur_bar_capacity < min_bars):
            valid_tokens.append(3)
        # value definition
        if seq_started and not seq_stopped:
            for t in range(5, 28 + 1):
                valid_tokens.append(t)
        # note
        if seq_started and not seq_stopped \
                and (not bar_limit_hard
                     or cur_bar_time + prv_value <= cur_bar_capacity
                     or cur_bar_index + 1 + (
                             prv_value - (cur_bar_capacity - cur_bar_time)) // cur_bar_capacity < min_bars):
            for t in range(29, 116 + 1):
                valid_tokens.append(t)
        # time signature
        if seq_started and not seq_stopped and cur_bar_time == 0:
            for t in range(117, 131 + 1):
                valid_tokens.append(t)

        state = {"cur_bar_index": cur_bar_index,
                 "cur_bar_capacity": cur_bar_capacity,
                 "cur_time": cur_time,
                 "cur_bar_time": cur_bar_time,
                 "prv_type": prv_type,
                 "prv_value": prv_value,
                 "seq_started": seq_started,
                 "seq_stopped": seq_stopped}

        return valid_tokens, state


class CoFNotelikeTokeniser(BaseNotelikeTokeniser):
    """Tokeniser that uses note-like temporal representation with circle of fifths distances between notes.

    [        0] ... pad
    [        1] ... start
    [        2] ... stop
    [        3] ... wait
    [  4 -  27] ... value definition
    [ 28 -  44] ... octave shift between notes
    [ 45 -  56] ... note without octave in distance on the circle of fifths
    [ 57 -  72] ... time signature numerator in eights from 2/8 to 16/8
    """

    def __init__(self, running_value: bool, running_octave: bool, running_time_sig: bool) -> None:
        super().__init__(running_value, running_time_sig)

        self.flags[Flags.RUNNING_OCTAVE] = running_octave

        self.prv_octave = None

    def reset_previous(self) -> None:
        super().reset_previous()

        # A4 as base note
        self.prv_note = 69
        self.prv_octave = 4

    def tokenise(self, sequence: Sequence, apply_buffer: bool = True, reset_base_note: bool = True,
                 reset_time: bool = True, insert_border_tokens: bool = False) -> list[int]:
        tokens = []
        event_pairings = sequence.abs.get_message_time_pairings(
            [MessageType.NOTE_ON, MessageType.NOTE_OFF, MessageType.TIME_SIGNATURE, MessageType.INTERNAL])

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

                # Check if octave of note hast to be defined
                octave_tgt = msg_note // 12 - 1
                if not (self.prv_octave == octave_tgt and self.flags.get(Flags.RUNNING_OCTAVE, False)):
                    octave_src = self.prv_note // 12 - 1
                    octave_shift = octave_tgt - octave_src
                    assert -8 <= octave_shift <= 8
                    tokens.append((octave_shift + 8) + 28)

                cof_dist = CircleOfFifths.get_distance(self.prv_note, msg_note)

                tokens.append((cof_dist + 5) + 45)

                self.cur_time_target = max(self.cur_time_target, self.cur_time + msg_value)
                self.prv_type = MessageType.NOTE_ON
                self.prv_note = msg_note
                self.prv_octave = octave_tgt
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
                    tokens.append(numerator - 2 + 57)

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

        if insert_border_tokens:
            tokens.insert(0, 1)
            tokens.append(2)

        return tokens

    @staticmethod
    def detokenise(tokens: list[int]) -> Sequence:
        seq = Sequence()
        cur_time = 0
        prv_type = None
        prv_note = 69  # A4 is base note
        prv_octave = 4
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
            elif 28 <= token <= 44:
                prv_octave += token - 28 - 8
            elif 45 <= token <= 56:
                note_base = CircleOfFifths.from_distance(prv_note, (token - 45) - 5)
                note = note_base + prv_octave * 12 + 12

                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_ON, note=note, time=cur_time))
                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_OFF, note=note, time=cur_time + prv_value))
                prv_type = MessageType.NOTE_ON
                prv_note = note
            elif 57 <= token <= 72:
                seq.add_absolute_message(
                    Message(message_type=MessageType.TIME_SIGNATURE, time=cur_time,
                            numerator=token - 57 + 2, denominator=8)
                )
                prv_type = MessageType.TIME_SIGNATURE
            else:
                raise TokenisationException(f"Encountered invalid token during detokenisation: {token}")

        return seq

    @staticmethod
    def get_info_notes(tokens: list[int], invalid_value: int = -1) -> list[int]:
        info = []
        prv_note = None

        for token in tokens:
            if token == 131:
                info.append(prv_note)
            elif not 28 <= token <= 115:
                info.append(invalid_value)
            else:
                info.append(token - 28 + 21)
                prv_note = token - 28 + 21

        return info

    @staticmethod
    def get_info_circle_of_fifths(tokens: list[int], invalid_value: int = -1) -> list[int]:
        info = []
        prv_note = None

        for token in tokens:
            if token == 131:
                info.append(prv_note % 12)
            elif not 28 <= token <= 115:
                info.append(invalid_value)
            else:
                info.append((token - 28 + 21) % 12)
                prv_note = token - 28 + 21

        return info

    @staticmethod
    def get_info_elapsed_ticks(tokens: list[int]) -> list[int]:
        info = []
        cur_time = 0
        prv_type = None
        prv_value = math.nan

        for token in tokens:
            info.append(cur_time)

            if token == 3:
                cur_time += prv_value
                prv_type = MessageType.WAIT
            elif 4 <= token <= 27:
                if prv_type == MessageType.INTERNAL:
                    prv_value += token - 3
                else:
                    prv_value = token - 3
                prv_type = MessageType.INTERNAL
            else:
                prv_type = "general_message"

        return info


class LargeDictionaryNotelikeTokeniser(BaseNotelikeTokeniser):
    """Tokeniser that uses note-like temporal representation.

    [        0] ... pad
    [        1] ... start
    [        2] ... stop
    [        3] ... bar seperator
    [  4 -  27] ... wait
    [ 28 - 115] ... notes with duration of 2 ticks
    [116 - 203] ... notes with duration of 3 ticks
    [204 - 291] ... notes with duration of 4 ticks
    [292 - 379] ... notes with duration of 6 ticks
    [380 - 467] ... notes with duration of 8 ticks
    [468 - 555] ... notes with duration of 9 ticks
    [556 - 643] ... notes with duration of 12 ticks
    [644 - 731] ... notes with duration of 16 ticks
    [732 - 819] ... notes with duration of 18 ticks
    [820 - 907] ... notes with duration of 24 ticks
    [908 - 995] ... notes with duration of 32 ticks
    [996 -1083] ... notes with duration of 36 ticks
    [1084-1171] ... notes with duration of 48 ticks
    [1172-1259] ... notes with duration of 64 ticks
    [1260-1347] ... notes with duration of 72 ticks
    [1348-1435] ... notes with duration of 96 ticks
    [1436-1450] ... time signature numerator in eights from 2/8 to 16/8
    """

    SUPPORTED_VALUES = [2, 3, 4, 6, 8, 9, 12, 16, 18, 24, 32, 36, 48, 64, 72, 96]

    def __init__(self, running_time_sig: bool) -> None:
        super().__init__(False, running_time_sig)

    def tokenise(self, sequence: Sequence, apply_buffer: bool = True, reset_time: bool = True,
                 insert_border_tokens: bool = False) -> list[int]:
        tokens = []
        event_pairings = sequence.abs.get_message_time_pairings(
            [MessageType.NOTE_ON, MessageType.NOTE_OFF, MessageType.TIME_SIGNATURE, MessageType.INTERNAL])

        for event_pairing in event_pairings:
            msg_type = event_pairing[0].message_type
            msg_time = event_pairing[0].time

            if msg_type == MessageType.NOTE_ON:
                msg_note = event_pairing[0].note
                msg_value = event_pairing[1].time - msg_time

                if not (21 <= msg_note <= 108):
                    raise TokenisationException(f"Invalid note: {msg_note}")
                if msg_value not in LargeDictionaryNotelikeTokeniser.SUPPORTED_VALUES:
                    raise TokenisationException(f"Invalid note value: {msg_value}")

                # Check if message occurs at current time, if not place rest messages
                if not self.cur_time == msg_time:
                    self.cur_rest_buffer += msg_time - self.cur_time
                    tokens.extend(
                        self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, value_shift=3))
                    self.cur_time += self.cur_rest_buffer
                    self.cur_rest_buffer = 0

                # Add token representing pitch and value
                tokens.append(
                    msg_note - 21 + 28 + LargeDictionaryNotelikeTokeniser.SUPPORTED_VALUES.index(msg_value) * 88)

                self.cur_time_target = max(self.cur_time_target, self.cur_time + msg_value)
            elif msg_type == MessageType.TIME_SIGNATURE:
                msg_numerator = event_pairing[0].numerator
                msg_denominator = event_pairing[0].denominator

                numerator = self._time_signature_to_eights(msg_numerator, msg_denominator)

                # Check if time signature has to be defined
                if not (self.prv_numerator == numerator and self.flags.get(Flags.RUNNING_TIME_SIG, False)):
                    self.cur_rest_buffer += msg_time - self.cur_time
                    tokens.extend(
                        self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, value_shift=3))
                    self.cur_time += self.cur_rest_buffer
                    self.cur_rest_buffer = 0
                    tokens.append(numerator - 2 + len(LargeDictionaryNotelikeTokeniser.SUPPORTED_VALUES) * 88 + 4 + 24)

                self.prv_numerator = numerator
            elif msg_type == MessageType.INTERNAL:
                self.cur_rest_buffer += msg_time - self.cur_time

        if apply_buffer:
            self.cur_rest_buffer = max(self.cur_time_target - self.cur_time, self.cur_rest_buffer)
            tokens.extend(
                self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, value_shift=3))
            self.cur_time += self.cur_rest_buffer
            self.cur_rest_buffer = 0

        if reset_time:
            self.reset_time()

        if insert_border_tokens:
            tokens.insert(0, 1)
            tokens.append(2)

        return tokens

    @staticmethod
    def detokenise(tokens: list[int]) -> Sequence:
        seq = Sequence()
        cur_time = 0

        boundary_token_ts = len(LargeDictionaryNotelikeTokeniser.SUPPORTED_VALUES) * 88 + 4 + 24

        for token in tokens:
            if token <= 2:
                pass
            elif 4 <= token <= 27:
                cur_time += token - 3
            elif 28 <= token <= boundary_token_ts - 1:
                note_pitch = (token - 28) % 88 + 21
                note_value = LargeDictionaryNotelikeTokeniser.SUPPORTED_VALUES[(token - 28) // 88]

                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_ON, note=note_pitch, time=cur_time))
                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_OFF, note=note_pitch, time=cur_time + note_value))
            elif boundary_token_ts <= token <= boundary_token_ts + 14:
                seq.add_absolute_message(
                    Message(message_type=MessageType.TIME_SIGNATURE, time=cur_time,
                            numerator=token - boundary_token_ts + 2,
                            denominator=8)
                )
            else:
                raise TokenisationException(f"Encountered invalid token during detokenisation: {token}")

        return seq
