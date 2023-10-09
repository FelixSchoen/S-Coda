import math
from abc import ABC, abstractmethod

from scoda.elements.message import Message
from scoda.exceptions.tokenisation_exception import TokenisationException
from scoda.sequences.sequence import Sequence
from scoda.settings.settings import PPQN
from scoda.utils.enumerations import MessageType, Flags
from scoda.utils.music_theory import CircleOfFifths


class Tokeniser(ABC):

    def __init__(self, running_time_sig: bool) -> None:
        super().__init__()

        self.flags = dict()
        self.flags[Flags.RUNNING_TIME_SIG] = running_time_sig

        self.cur_time = None
        self.cur_time_target = None
        self.cur_rest_buffer = None

        self.prv_type = None
        self.prv_note = None
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
    def tokenise(self, sequence: Sequence, insert_border_tokens: bool = False) -> list[int]:
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
                f"Invalid time signature numerator: {scaled}")

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
    [      131] ... note with previous pitch (running pitch only)
    """

    def __init__(self, running_value: bool, running_pitch: bool, running_time_sig: bool) -> None:
        super().__init__(running_time_sig)

        self.flags[Flags.RUNNING_VALUE] = running_value
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
                        self._notelike_tokenise_flush_rest_buffer(apply_target=False, wait_token=3, value_shift=3))

                # Check if value of note has to be defined
                if not (self.prv_value == msg_value and self.flags.get(Flags.RUNNING_VALUE, False)):
                    tokens.extend(self._general_tokenise_flush_time_buffer(msg_value, value_shift=3))

                # Check if pitch of note has to be defined
                if not (self.prv_note == msg_note and self.flags.get(Flags.RUNNING_PITCH, False)):
                    tokens.append(msg_note - 21 + 28)
                else:
                    tokens.append(131)

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
                prv_note = token - 28 + 21
            elif 116 <= token <= 130:
                seq.add_absolute_message(
                    Message(message_type=MessageType.TIME_SIGNATURE, time=cur_time,
                            numerator=token - 116 + 2, denominator=8)
                )
                prv_type = MessageType.TIME_SIGNATURE
            elif token == 131:
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
            elif 4 <= token <= 27:
                if prv_type == MessageType.INTERNAL:
                    prv_value += token - 3
                else:
                    prv_value = token - 3
                prv_type = MessageType.INTERNAL
            elif 28 <= token <= 115:
                prv_type = MessageType.NOTE_ON
                prv_note = token - 28 + 21
            elif 116 <= token <= 130:
                cur_bar_capacity = int(((token - 116 + 2) / 8) * PPQN)
                prv_type = MessageType.TIME_SIGNATURE
            elif token == 131:
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
            for t in range(4, 27 + 1):
                valid_tokens.append(t)
        # note
        if seq_started and not seq_stopped \
                and (not bar_limit_hard
                     or cur_bar_time + prv_value <= cur_bar_capacity
                     or cur_bar_index + 1 + (
                             prv_value - (cur_bar_capacity - cur_bar_time)) // cur_bar_capacity < min_bars):
            for t in range(28, 115 + 1):
                valid_tokens.append(t)
        # time signature
        if seq_started and not seq_stopped and cur_bar_time == 0:
            for t in range(116, 130 + 1):
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


class CoFNotelikeTokeniser(Tokeniser):
    """Tokeniser that uses note-like temporal representation with circle of fifths distances between notes.

    [        0] ... pad
    [        1] ... start
    [        2] ... stop
    [        3] ... wait
    [  4 -  27] ... value definition
    [ 28 - 231] ... note in relative octaves and circle of fifths distances
    [232 - 247] ... time signature numerator in eights from 2/8 to 16/8
    """

    def __init__(self, running_value: bool, running_time_sig: bool) -> None:
        super().__init__(running_time_sig)

        self.flags[Flags.RUNNING_VALUE] = running_value

    def tokenise(self, sequence: Sequence, apply_buffer: bool = True, reset_base_note: bool = True,
                 reset_time: bool = True, insert_border_tokens: bool = False) -> list[int]:
        tokens = []
        event_pairings = sequence.abs.get_message_time_pairings(
            [MessageType.NOTE_ON, MessageType.NOTE_OFF, MessageType.TIME_SIGNATURE, MessageType.INTERNAL])
        self.prv_note = 69  # A1 as base note

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

                cof_dist = CircleOfFifths.get_distance(self.prv_note, msg_note)
                octave_src = self.prv_note // 12 - 1
                octave_trg = msg_note // 12 - 1
                octave_shift = octave_trg - octave_src

                assert -8 <= octave_shift <= 8

                tokens.append(((octave_shift + 8) * 12) + (cof_dist + 5) + 28)

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
                    tokens.append(numerator - 2 + 232)

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
        prv_note = 69  # A1 is base note
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
            elif 28 <= token <= 231:
                octave_shift = (token - 28) // 12 - 8
                note_base = CircleOfFifths.from_distance(prv_note, (token - 28) % 12 - 5)
                note = note_base + ((prv_note // 12 + octave_shift) * 12)

                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_ON, note=note, time=cur_time))
                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_OFF, note=note, time=cur_time + prv_value))
                prv_type = MessageType.NOTE_ON
                prv_note = note
            elif 232 <= token <= 247:
                seq.add_absolute_message(
                    Message(message_type=MessageType.TIME_SIGNATURE, time=cur_time,
                            numerator=token - 116 + 2, denominator=8)
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
            elif 4 <= token <= 27:
                if prv_type == MessageType.INTERNAL:
                    prv_value += token - 3
                else:
                    prv_value = token - 3
                prv_type = MessageType.INTERNAL
            elif 28 <= token <= 115:
                prv_type = MessageType.NOTE_ON
                prv_note = token - 28 + 21
            elif 116 <= token <= 130:
                cur_bar_capacity = int(((token - 116 + 2) / 8) * PPQN)
                prv_type = MessageType.TIME_SIGNATURE
            elif token == 131:
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
            for t in range(4, 27 + 1):
                valid_tokens.append(t)
        # note
        if seq_started and not seq_stopped \
                and (not bar_limit_hard
                     or cur_bar_time + prv_value <= cur_bar_capacity
                     or cur_bar_index + 1 + (
                             prv_value - (cur_bar_capacity - cur_bar_time)) // cur_bar_capacity < min_bars):
            for t in range(28, 115 + 1):
                valid_tokens.append(t)
        # time signature
        if seq_started and not seq_stopped and cur_bar_time == 0:
            for t in range(116, 130 + 1):
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

    def tokenise(self, bar_seq: Sequence, apply_buffer: bool = True, insert_border_tokens: bool = False) -> list[int]:
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

        if insert_border_tokens:
            tokens.insert(0, 1)
            tokens.append(2)

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
        prv_type = None
        min_grid_size = math.nan

        for token in tokens:
            info.append(cur_time)

            if token == 3:
                if math.isnan(min_grid_size):
                    raise TokenisationException(f"Grid size not initialised")

                cur_time += min_grid_size
                prv_type = MessageType.INTERNAL
            elif 4 <= token <= 27:
                if prv_type == MessageType.WAIT:
                    raise TokenisationException(f"Illegal consecutive grid size definition")

                min_grid_size = token - 3
                prv_type = MessageType.WAIT
            else:
                prv_type = "general_message"

        return info


class TransposedNotelikeTokeniser(Tokeniser):
    """Tokeniser that uses transposed temporal representation with a note-like approach, i.e., all occurrences of a note
    are shown first before any other note is handled. Note that an input sequence is required to represent a list of bars,
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

        self.flags[Flags.RUNNING_VALUE] = running_value

    def tokenise(self, bar_seq: Sequence, apply_buffer: bool = True, reset_time: bool = True,
                 insert_border_tokens: bool = False) -> list[int]:
        tokens = []
        event_pairings = bar_seq.abs.get_message_time_pairings(
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

    @staticmethod
    def get_info_notes(tokens: list[int], invalid_value: int = -1) -> list[int]:
        info = []

        prv_note = math.nan

        for token in tokens:
            if token == 3:
                if math.isnan(prv_note):
                    raise TokenisationException(f"Note value not initialised")

                info.append(prv_note)
            elif 30 <= token <= 117:
                info.append(invalid_value)
                prv_note = token - 30 + 21
            else:
                info.append(invalid_value)

        return info

    @staticmethod
    def get_info_circle_of_fifths(tokens: list[int], invalid_value: int = -1) -> list[int]:
        info = []

        prv_note = math.nan

        for token in tokens:
            if token == 3:
                if math.isnan(prv_note):
                    raise TokenisationException(f"Note value not initialised")

                info.append(prv_note % 12)
            elif 30 <= token <= 117:
                info.append(invalid_value)
                prv_note = token - 30 + 21
            else:
                info.append(invalid_value)

        return info

    @staticmethod
    def get_info_elapsed_ticks(tokens: list[int]) -> list[int]:
        info = []

        time_bar_start = 0
        cur_time_bar = 0

        prv_type = None
        prv_value = math.nan
        prv_numerator = math.nan

        for token in tokens:
            info.append(time_bar_start + cur_time_bar)

            if token == 4:
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

                prv_type = "note_definition"
            elif 118 <= token <= 132:
                numerator = token - 118 + 2

                prv_type = MessageType.TIME_SIGNATURE
                prv_numerator = numerator
            else:
                prv_type = "general_message"

        return info
