import math
from abc import ABC, abstractmethod
from typing import Any

from scoda.elements.message import Message
from scoda.enumerations.message_type import MessageType
from scoda.enumerations.tokenisation_flags import TokenisationFlags
from scoda.exceptions.tokenisation_exception import TokenisationException
from scoda.misc.music_theory import CircleOfFifths
from scoda.sequences.sequence import Sequence
from scoda.settings.settings import PPQN
from scoda.tokenisation.base_tokenisation import BaseTokeniser


class BaseNotelikeTokeniser(BaseTokeniser, ABC):

    def __init__(self, running_value: bool, running_time_sig: bool) -> None:
        super().__init__()

        self.flags[TokenisationFlags.RUNNING_VALUE] = running_value
        self.flags[TokenisationFlags.RUNNING_TIME_SIG] = running_time_sig


class BaseLargeDictionaryNotelikeTokeniser(BaseNotelikeTokeniser, ABC):
    SUPPORTED_VALUES = [2, 3, 4, 6, 8, 9, 12, 16, 18, 24, 32, 36, 48, 64, 72, 96]
    NOTE_SECTION_SIZE = None

    def __init__(self, running_time_sig: bool) -> None:
        super().__init__(False, running_time_sig)

    def tokenise(self, sequence: Sequence, apply_buffer: bool = True, reset_time: bool = True) -> list[int]:
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
                        self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, index_time_def=4))
                    self.cur_time += self.cur_rest_buffer
                    self.cur_rest_buffer = 0

                # Callback
                self._tokenise_note(tokens, msg_note, msg_value)

                self.cur_time_target = max(self.cur_time_target, self.cur_time + msg_value)
                self.prv_note = msg_note
            elif msg_type == MessageType.TIME_SIGNATURE:
                msg_numerator = event_pairing[0].numerator
                msg_denominator = event_pairing[0].denominator

                numerator = self._time_signature_to_eights(msg_numerator, msg_denominator)

                # Check if time signature has to be defined
                if not (self.prv_numerator == numerator and self.flags.get(TokenisationFlags.RUNNING_TIME_SIG, False)):
                    self.cur_rest_buffer += msg_time - self.cur_time
                    tokens.extend(
                        self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, index_time_def=4))
                    self.cur_time += self.cur_rest_buffer
                    self.cur_rest_buffer = 0

                    tokens.append(numerator - 2 + len(self.SUPPORTED_VALUES) * self.NOTE_SECTION_SIZE + 4 + 24)

                self.prv_numerator = numerator
            elif msg_type == MessageType.INTERNAL:
                self.cur_rest_buffer += msg_time - self.cur_time

        if apply_buffer:
            self.cur_rest_buffer = max(self.cur_time_target - self.cur_time, self.cur_rest_buffer)
            tokens.extend(
                self._general_tokenise_flush_time_buffer(time=self.cur_rest_buffer, index_time_def=4))
            self.cur_time += self.cur_rest_buffer
            self.cur_rest_buffer = 0

        if reset_time:
            self.reset_time()

        return tokens

    @abstractmethod
    def _tokenise_note(self, tokens: list[int], msg_note: int, msg_value: int) -> None:
        pass


class StandardNotelikeTokeniser(BaseNotelikeTokeniser):
    """Tokeniser that uses note-like temporal representation.

    [        0] ... pad
    [        1] ... start
    [        2] ... stop
    [        3] ... bar separator
    [        4] ... wait
    [  5 -  28] ... value definition
    [ 29 - 116] ... note
    [117 - 131] ... time signature numerator in eights from 2/8 to 16/8
    [      132] ... note with previous pitch (running pitch only)
    """

    def __init__(self, running_value: bool, running_pitch: bool, running_time_sig: bool) -> None:
        super().__init__(running_value, running_time_sig)

        self.flags[TokenisationFlags.RUNNING_PITCH] = running_pitch

    def tokenise(self, sequence: Sequence, apply_buffer: bool = True, reset_time: bool = True) -> list[int]:
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
                        self._notelike_tokenise_flush_rest_buffer(apply_target=False, wait_token=4, index_time_def=5))

                # Check if value of note has to be defined
                if not (self.prv_value == msg_value and self.flags.get(TokenisationFlags.RUNNING_VALUE, False)):
                    tokens.extend(self._general_tokenise_flush_time_buffer(msg_value, index_time_def=5))

                # Check if pitch of note has to be defined
                if not (self.prv_note == msg_note and self.flags.get(TokenisationFlags.RUNNING_PITCH, False)):
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
                if not (self.prv_numerator == numerator and self.flags.get(TokenisationFlags.RUNNING_TIME_SIG, False)):
                    self.cur_rest_buffer += msg_time - self.cur_time
                    tokens.extend(
                        self._notelike_tokenise_flush_rest_buffer(apply_target=False, wait_token=4, index_time_def=5))
                    tokens.append(numerator - 2 + 117)

                self.prv_type = MessageType.TIME_SIGNATURE
                self.prv_numerator = numerator
            elif msg_type == MessageType.INTERNAL:
                self.cur_rest_buffer += msg_time - self.cur_time
                self.prv_type = MessageType.INTERNAL

        if apply_buffer:
            tokens.extend(
                self._notelike_tokenise_flush_rest_buffer(apply_target=True, wait_token=4, index_time_def=5))

        if reset_time:
            self.reset_time()

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
                prv_type = "sequence_control"
            elif token == 4:
                cur_time += prv_value
                prv_type = MessageType.WAIT
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

    def get_constraints(self, tokens: list[int], previous_state: dict = None, min_bars: int = -1) -> \
            tuple[list[int], dict[str, Any]]:
        running_value = self.flags.get(TokenisationFlags.RUNNING_VALUE, False)
        running_pitch = self.flags.get(TokenisationFlags.RUNNING_PITCH, False)
        running_time_sig = self.flags.get(TokenisationFlags.RUNNING_TIME_SIG, False)

        cur_time = 0
        cur_bar = 0
        bar_time = 0
        bar_tokens = []
        bar_capacity = None
        pnt_concurrent_notes = []
        seq_started = False
        seq_stopped = False
        prv_type = None
        prv_note = None
        prv_value = math.nan

        if previous_state is not None:
            cur_time = previous_state["cur_time"]
            cur_bar = previous_state["cur_bar"]
            bar_time = previous_state["bar_time"]
            bar_tokens = previous_state["bar_tokens"]
            pnt_concurrent_notes = previous_state["pnt_concurrent_notes"]
            bar_capacity = previous_state["bar_capacity"]
            seq_started = previous_state["seq_started"]
            seq_stopped = previous_state["seq_stopped"]
            prv_type = previous_state["prv_type"]
            prv_note = previous_state["prv_note"]
            prv_value = previous_state["prv_value"]

        # === Retrace sequence ===

        for token in tokens:
            if token == 0:
                bar_tokens.append(token)
                prv_type = MessageType.SEQUENCE_CONTROL
            elif token == 1:
                bar_tokens.append(token)
                seq_started = True
                prv_type = MessageType.SEQUENCE_CONTROL
            elif token == 2:
                bar_tokens.append(token)
                seq_stopped = True
                prv_type = MessageType.SEQUENCE_CONTROL
            elif token == 3:
                cur_bar += 1
                bar_time = 0
                bar_tokens.append(token)
                prv_type = MessageType.SEQUENCE_CONTROL
            elif token == 4:
                cur_time += prv_value
                bar_time += prv_value

                while bar_time > bar_capacity:
                    bar_time -= bar_capacity
                    cur_bar += 1

                bar_tokens.append(token)
                pnt_concurrent_notes = []
                prv_type = MessageType.WAIT

            elif 5 <= token <= 28:
                bar_tokens.append(token)
                if prv_type != MessageType.INTERNAL:
                    prv_value = 0
                prv_value += token - 4
                prv_type = MessageType.INTERNAL
            elif 29 <= token <= 116:
                bar_tokens.append(token)
                pnt_concurrent_notes.append(token - 29 + 21)
                prv_type = MessageType.NOTE_ON
                prv_note = token - 29 + 21
            elif 117 <= token <= 131:
                bar_tokens.append(token)
                bar_capacity = int(((token - 117 + 2) / 8) * 4 * PPQN)
                prv_type = MessageType.TIME_SIGNATURE
            elif token == 132:
                bar_tokens.append(token)
                pnt_concurrent_notes.append(prv_note)
                prv_type = MessageType.NOTE_ON
            else:
                raise TokenisationException(f"Encountered invalid token during constraint creation: {token}")

            if not running_value and not 5 <= token <= 28:
                prv_value = None

        # === Retrieve valid tokens ===

        # Helper variables
        h_started_not_stopped = seq_started and not seq_stopped
        h_bar_contains_time_signature = any(117 <= t <= 131 for t in bar_tokens)
        h_bar_valid_time_signature = (running_time_sig and bar_capacity is not None) or h_bar_contains_time_signature
        h_note_not_open = lambda x: x is not None and x not in pnt_concurrent_notes
        h_has_prv_value = prv_value is not None

        valid_tokens = []

        # [        0] ... pad
        if seq_started and seq_stopped:
            valid_tokens.append(0)
        # [        1] ... start
        if not seq_started:
            valid_tokens.append(1)
        # [        2] ... stop
        if not seq_stopped and (min_bars == -1 or cur_bar + 1 == min_bars) and bar_time == bar_capacity:
            valid_tokens.append(2)
        # [        3] ... bar separator
        if h_started_not_stopped and h_bar_valid_time_signature and bar_time == bar_capacity and 3 not in bar_tokens:
            valid_tokens.append(3)
        # [        4] ... wait
        if h_started_not_stopped and h_bar_valid_time_signature and h_has_prv_value and bar_capacity - bar_time >= prv_value:
            valid_tokens.append(4)
        # [  5 -  28] ... value definition
        if h_started_not_stopped and h_bar_valid_time_signature:
            prv_value_volatile = prv_value
            if prv_type != MessageType.INTERNAL:
                prv_value_volatile = 0
            for v_d in range(1, 24 + 1):
                if bar_capacity - bar_time >= prv_value_volatile + v_d:
                    valid_tokens.append(v_d + 4)
        # [ 29 - 116] ... note
        if h_started_not_stopped and h_bar_valid_time_signature and h_has_prv_value:
            for n in range(21, 108 + 1):
                if n not in pnt_concurrent_notes:
                    valid_tokens.append(n - 21 + 29)
        # [117 - 131] ... time signature numerator in eights from 2/8 to 16/8
        if h_started_not_stopped and not h_bar_contains_time_signature and bar_time == 0:
            for t in range(117, 131 + 1):
                valid_tokens.append(t)
        # [      132] ... note with previous pitch (running pitch only)
        if h_started_not_stopped and h_bar_valid_time_signature and running_pitch and h_has_prv_value and h_note_not_open(
                prv_note):
            valid_tokens.append(132)

        # === Store and return finding ===

        state = {"cur_time": cur_time,
                 "cur_bar": cur_bar,
                 "bar_time": bar_time,
                 "bar_tokens": bar_tokens,
                 "pnt_concurrent_notes": pnt_concurrent_notes,
                 "bar_capacity": bar_capacity,
                 "seq_started": seq_started,
                 "seq_stopped": seq_stopped,
                 "prv_type": prv_type,
                 "prv_note": prv_note,
                 "prv_value": prv_value}

        return valid_tokens, state


class LargeDictionaryNotelikeTokeniser(BaseLargeDictionaryNotelikeTokeniser):
    """Tokeniser that uses note-like temporal representation.

    [        0] ... pad
    [        1] ... start
    [        2] ... stop
    [        3] ... bar separator
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

    def __init__(self, running_time_sig: bool) -> None:
        super().__init__(running_time_sig)

    NOTE_SECTION_SIZE = 88

    def _tokenise_note(self, tokens: list[int], msg_note: int, msg_value: int) -> None:
        # Add token representing pitch and value
        tokens.append(
            msg_note - 21 + 28 + LargeDictionaryNotelikeTokeniser.SUPPORTED_VALUES.index(msg_value) * 88)

    @staticmethod
    def detokenise(tokens: list[int]) -> Sequence:
        seq = Sequence()
        cur_time = 0
        note_section_size = LargeDictionaryNotelikeTokeniser.NOTE_SECTION_SIZE

        boundary_token_ts = len(LargeDictionaryNotelikeTokeniser.SUPPORTED_VALUES) * note_section_size + 4 + 24

        for token in tokens:
            if token <= 3:
                pass
            elif 4 <= token <= 27:
                cur_time += token - 3
            elif 28 <= token <= boundary_token_ts - 1:
                note_pitch = (token - 28) % note_section_size + 21
                note_value = LargeDictionaryNotelikeTokeniser.SUPPORTED_VALUES[(token - 28) // note_section_size]

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


class CoFNotelikeTokeniser(BaseNotelikeTokeniser):
    """Tokeniser that uses note-like temporal representation with circle of fifths distances between notes.

    [        0] ... pad
    [        1] ... start
    [        2] ... stop
    [        3] ... bar separator
    [        4] ... wait
    [  5 -  28] ... value definition
    [ 29 -  45] ... octave shift between notes
    [ 46 -  57] ... note without octave in distance on the circle of fifths
    [ 58 -  73] ... time signature numerator in eights from 2/8 to 16/8
    """

    def __init__(self, running_value: bool, running_octave: bool, running_time_sig: bool) -> None:
        super().__init__(running_value, running_time_sig)

        self.flags[TokenisationFlags.RUNNING_OCTAVE] = running_octave

        self.prv_octave = None

    def reset_previous(self) -> None:
        super().reset_previous()

        # A4 as base note
        self.prv_note = 69
        self.prv_octave = 4

    def tokenise(self, sequence: Sequence, apply_buffer: bool = True, reset_base_note: bool = True,
                 reset_time: bool = True) -> list[int]:
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
                        self._notelike_tokenise_flush_rest_buffer(apply_target=False, wait_token=4, index_time_def=5))

                # Check if value of note has to be defined
                if not (self.prv_value == msg_value and self.flags.get(TokenisationFlags.RUNNING_VALUE, False)):
                    tokens.extend(self._general_tokenise_flush_time_buffer(msg_value, index_time_def=5))

                # Get distances
                octave_tgt = msg_note // 12 - 1
                octave_src = self.prv_note // 12 - 1
                octave_shift = octave_tgt - octave_src
                assert -8 <= octave_shift <= 8

                cof_dist = CircleOfFifths.get_distance(self.prv_note, msg_note)
                assert -5 <= cof_dist <= 6

                # Insert octave shift (if necessary) and note distance
                if not (self.prv_octave == octave_tgt and self.flags.get(TokenisationFlags.RUNNING_OCTAVE, False)):
                    tokens.append((octave_shift + 8) + 29)
                tokens.append((cof_dist + 5) + 46)

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
                if not (self.prv_numerator == numerator and self.flags.get(TokenisationFlags.RUNNING_TIME_SIG, False)):
                    self.cur_rest_buffer += msg_time - self.cur_time
                    tokens.extend(
                        self._notelike_tokenise_flush_rest_buffer(apply_target=False, wait_token=4, index_time_def=5))
                    tokens.append(numerator - 2 + 58)

                self.prv_type = MessageType.TIME_SIGNATURE
                self.prv_numerator = numerator
            elif msg_type == MessageType.INTERNAL:
                self.cur_rest_buffer += msg_time - self.cur_time
                self.prv_type = MessageType.INTERNAL

        if apply_buffer:
            tokens.extend(
                self._notelike_tokenise_flush_rest_buffer(apply_target=True, wait_token=4, index_time_def=5))

        if reset_time:
            self.reset_time()

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
                prv_type = "sequence_control"
            elif token == 4:
                cur_time += prv_value
                prv_type = MessageType.WAIT
            elif 5 <= token <= 28:
                if prv_type == MessageType.INTERNAL:
                    prv_value += token - 4
                else:
                    prv_value = token - 4
                prv_type = MessageType.INTERNAL
            elif 29 <= token <= 45:
                prv_octave += token - 29 - 8
            elif 46 <= token <= 57:
                note_base = CircleOfFifths.from_distance(prv_note, (token - 46) - 5)
                note = note_base + prv_octave * 12 + 12  # Shifts notes to A0

                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_ON, note=note, time=cur_time))
                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_OFF, note=note, time=cur_time + prv_value))
                prv_type = MessageType.NOTE_ON
                prv_note = note
            elif 58 <= token <= 73:
                seq.add_absolute_message(
                    Message(message_type=MessageType.TIME_SIGNATURE, time=cur_time,
                            numerator=token - 58 + 2, denominator=8)
                )
                prv_type = MessageType.TIME_SIGNATURE
            else:
                raise TokenisationException(f"Encountered invalid token during detokenisation: {token}")

        return seq


class LargeDictionaryCoFNotelikeTokeniser(BaseLargeDictionaryNotelikeTokeniser):
    """Tokeniser that uses note-like temporal representation with circle of fifths distances between notes.

    [        0] ... pad
    [        1] ... start
    [        2] ... stop
    [        3] ... bar separator
    [  4 -  27] ... wait
    [ 28 - 231] ... notes with duration of 2 ticks
    [232 - 435] ... notes with duration of 3 ticks
    [436 - 639] ... notes with duration of 4 ticks
    [640 - 843] ... notes with duration of 6 ticks
    [844 -1047] ... notes with duration of 8 ticks
    [1048-1251] ... notes with duration of 9 ticks
    [1252-1455] ... notes with duration of 12 ticks
    [1456-1659] ... notes with duration of 16 ticks
    [1660-1863] ... notes with duration of 18 ticks
    [1864-2067] ... notes with duration of 24 ticks
    [2068-2271] ... notes with duration of 32 ticks
    [2272-2475] ... notes with duration of 36 ticks
    [2476-2679] ... notes with duration of 48 ticks
    [2680-2883] ... notes with duration of 64 ticks
    [2884-3087] ... notes with duration of 72 ticks
    [3088-3291] ... notes with duration of 96 ticks
    [3292-3307] ... time signature numerator in eights from 2/8 to 16/8
    """

    def __init__(self, running_time_sig: bool) -> None:
        super().__init__(running_time_sig)

        self.prv_octave = None

    NOTE_SECTION_SIZE = 204

    def reset_previous(self) -> None:
        super().reset_previous()

        # A4 as base note
        self.prv_note = 69
        self.prv_octave = 4

    def _tokenise_note(self, tokens: list[int], msg_note: int, msg_value: int) -> None:
        # Get distances
        octave_tgt = msg_note // 12 - 1
        octave_src = self.prv_note // 12 - 1
        octave_shift = octave_tgt - octave_src
        assert -8 <= octave_shift <= 8

        cof_dist = CircleOfFifths.get_distance(self.prv_note, msg_note)
        assert -5 <= cof_dist <= 6

        token_value = (28 +
                       (cof_dist + 5) +
                       ((octave_shift + 8) * 12) +
                       self.SUPPORTED_VALUES.index(msg_value) * LargeDictionaryCoFNotelikeTokeniser.NOTE_SECTION_SIZE)

        tokens.append(token_value)

    @staticmethod
    def detokenise(tokens: list[int]) -> Sequence:
        seq = Sequence()
        cur_time = 0
        prv_note = 69  # A4 is base note
        note_section_size = LargeDictionaryCoFNotelikeTokeniser.NOTE_SECTION_SIZE

        boundary_token_ts = len(
            LargeDictionaryNotelikeTokeniser.SUPPORTED_VALUES) * note_section_size + 4 + 24

        for token in tokens:
            if token <= 3:
                pass
            elif 4 <= token <= 27:
                cur_time += token - 3
            elif 28 <= token <= boundary_token_ts - 1:
                note_cof_distance = ((token - 28) % note_section_size) % 12 - 5
                note_octave_shift = ((token - 28) % note_section_size) // 12 - 8
                note_value = LargeDictionaryNotelikeTokeniser.SUPPORTED_VALUES[(token - 28) // note_section_size]

                octave = prv_note // 12 - 1
                octave += note_octave_shift
                note_base = CircleOfFifths.from_distance(prv_note, note_cof_distance)
                note = note_base + octave * 12 + 12  # Shifts notes to A0

                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_ON, note=note, time=cur_time))
                seq.add_absolute_message(
                    Message(message_type=MessageType.NOTE_OFF, note=note, time=cur_time + note_value))
                prv_note = note
            elif boundary_token_ts <= token <= boundary_token_ts + 14:
                seq.add_absolute_message(
                    Message(message_type=MessageType.TIME_SIGNATURE, time=cur_time,
                            numerator=token - boundary_token_ts + 2,
                            denominator=8)
                )
            else:
                raise TokenisationException(f"Encountered invalid token during detokenisation: {token}")

        return seq
