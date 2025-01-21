import math
from abc import ABC, abstractmethod
from typing import Tuple, List, Any

import numpy as np

from scoda.elements.message import Message
from scoda.enumerations.message_type import MessageType
from scoda.enumerations.tokenisation_flags import TokenisationFlags
from scoda.enumerations.tokenisation_prefixes import TokenisationPrefixes
from scoda.exceptions.tokenisation_exception import TokenisationException
from scoda.misc.music_theory import CircleOfFifths
from scoda.misc.scoda_logging import get_logger
from scoda.misc.util import get_default_step_sizes, get_default_note_values, get_velocity_bins, bin_velocity
from scoda.sequences.sequence import Sequence
from scoda.settings.settings import PPQN, DEFAULT_TIME_SIGNATURE_NUMERATOR, DEFAULT_TIME_SIGNATURE_DENOMINATOR

LOGGER = get_logger(__name__)


class MultiTrackLargeVocabularyNotelikeTokeniser:

    def __init__(self,
                 ppqn: int = None,
                 num_instruments: int = 1,
                 pitch_range: Tuple[int, int] = (21, 108),
                 step_sizes: list[int] = None,
                 note_values: list[int] = None,
                 velocity_bins: int = 1,
                 time_signature_range: Tuple[int, int] = (2, 16)):
        self.dictionary = dict()
        self.inverse_dictionary = dict()
        self.dictionary_size = 0

        self.ppqn = ppqn
        self.step_sizes = step_sizes
        self.note_values = note_values
        self.num_instruments = num_instruments
        self.pitch_range = pitch_range
        self.time_signature_range = time_signature_range

        # Default Values
        if self.ppqn is None:
            self.ppqn = PPQN
        if self.step_sizes is None:
            self.step_sizes = get_default_step_sizes(lower_bound_shift=1)
        self.step_sizes.sort()
        if self.note_values is None:
            self.note_values = get_default_note_values()
        self.note_values.sort()

        self.velocity_bins = get_velocity_bins(velocity_bins=velocity_bins)

        # Memory
        self.cur_time = None
        self.cur_rest_buffer = None

        # Construct dictionary
        self._construct_dictionary()

        self.reset()

    def reset(self) -> None:
        self.cur_time = 0
        self.cur_rest_buffer = 0

    def tokenise(self, sequences_bar: list[Sequence], insert_bar_token: bool = True, reset_time: bool = True) -> List[
        str]:
        tokens = []

        # Merge sequences
        for i, sequence_bar in enumerate(sequences_bar):
            for msg in sequence_bar.abs.messages:
                msg.instrument = i
        sequence_bar = Sequence()
        sequence_bar.merge(sequences_bar)

        event_pairings = sequence_bar.abs.get_message_time_pairings(
            [MessageType.NOTE_ON, MessageType.NOTE_OFF, MessageType.TIME_SIGNATURE, MessageType.INTERNAL])

        for event_pairing in event_pairings:
            msg_type = event_pairing[0].message_type
            msg_time = event_pairing[0].time

            # Check if message occurs at current time, if not place rest messages
            if not self.cur_time == msg_time:
                tokens.extend(self._flush_buffer(msg_time - self.cur_time))
                self.cur_time = msg_time
                self.cur_rest_buffer = 0

            if msg_type == MessageType.NOTE_ON:
                msg_instrument = event_pairing[0].instrument
                msg_note = event_pairing[0].note
                msg_value = event_pairing[1].time - msg_time
                msg_velocity = self.velocity_bins[bin_velocity(event_pairing[0].velocity, self.velocity_bins)]

                if not (self.pitch_range[0] <= msg_note <= self.pitch_range[1]):
                    raise TokenisationException(f"Invalid note pitch: {msg_note}")
                if msg_value not in self.note_values:
                    raise TokenisationException(f"Invalid note value: {msg_value}")

                tokens.append(f"{TokenisationPrefixes.INSTRUMENT.value}_{msg_instrument:02}-"
                              f"{TokenisationPrefixes.PITCH.value}_{msg_note:03}-"
                              f"{TokenisationPrefixes.VALUE.value}_{msg_value:02}-"
                              f"{TokenisationPrefixes.VELOCITY.value}_{msg_velocity:03}")
            elif msg_type == MessageType.TIME_SIGNATURE:
                msg_numerator = event_pairing[0].numerator
                msg_denominator = event_pairing[0].denominator

                scaled = msg_numerator * (DEFAULT_TIME_SIGNATURE_DENOMINATOR / msg_denominator)
                if not float(scaled).is_integer():
                    raise TokenisationException(
                        f"Time signature {int(msg_numerator)}/{int(msg_denominator)} cannot be represented as multiples of eights")
                scaled = int(scaled)
                if not self.time_signature_range[0] <= scaled <= self.time_signature_range[1]:
                    raise TokenisationException(f"Invalid time signature numerator: {scaled}")

                tokens.append(
                    f"{TokenisationPrefixes.TIME_SIGNATURE.value}_{scaled:02}_{DEFAULT_TIME_SIGNATURE_NUMERATOR:02}")

        if insert_bar_token:
            tokens.append(TokenisationPrefixes.BAR.value)

        if reset_time:
            self.reset()

        return tokens

    def detokenise(self, tokens: List[str]) -> List[Sequence]:
        # Setup Values
        sequences = [Sequence() for _ in range(self.num_instruments)]
        cur_time = 0
        cur_time_bar = 0
        cur_time_signature_numerator = DEFAULT_TIME_SIGNATURE_NUMERATOR
        cur_time_signature_denominator = DEFAULT_TIME_SIGNATURE_DENOMINATOR
        cur_bar_capacity_total = int(self.ppqn * 4 * cur_time_signature_numerator / cur_time_signature_denominator)
        cur_bar_capacity_remaining = cur_bar_capacity_total

        for token in tokens:
            token_parts = self._split_token(token)
            part_main = token_parts[0][0]

            if part_main == TokenisationPrefixes.BAR.value:
                cur_time += cur_bar_capacity_remaining
                cur_time_bar = 0
                cur_bar_capacity_remaining = cur_bar_capacity_total

                for sequence in sequences:
                    sequence.add_absolute_message(Message(message_type=MessageType.INTERNAL, time=cur_time))
            elif part_main == TokenisationPrefixes.REST.value:
                cur_time += int(token_parts[0][1])
                cur_time_bar += int(token_parts[0][1])
                cur_bar_capacity_remaining -= int(token_parts[0][1])
            elif part_main == TokenisationPrefixes.INSTRUMENT.value:
                note_instrument = int(token_parts[0][1])
                note_pitch = int(token_parts[1][1])
                note_value = int(token_parts[2][1])
                note_velocity = int(token_parts[3][1])

                sequences[note_instrument].add_absolute_message(
                    Message(message_type=MessageType.NOTE_ON, note=note_pitch, time=cur_time, velocity=note_velocity)
                )
                sequences[note_instrument].add_absolute_message(
                    Message(message_type=MessageType.NOTE_OFF, note=note_pitch, time=cur_time + note_value)
                )
            elif part_main == TokenisationPrefixes.TIME_SIGNATURE.value:
                if cur_time_bar > 0:
                    LOGGER.warning(
                        f"Skipping time signature change mid-bar at time {cur_time} (bar time {cur_time_bar})")
                else:
                    cur_time_signature_numerator = int(token_parts[0][1])
                    cur_time_signature_denominator = int(token_parts[0][2])
                    cur_bar_capacity_total = int(
                        self.ppqn * 4 * cur_time_signature_numerator / cur_time_signature_denominator)
                    cur_bar_capacity_remaining = cur_bar_capacity_total
            else:
                raise TokenisationException(f"Invalid token: {token}")

        return sequences

    def encode(self, tokens: List[str]) -> List[int]:
        return [self.dictionary[token] for token in tokens]

    def decode(self, tokens: List[int]) -> List[str]:
        return [self.inverse_dictionary[token] for token in tokens]

    def get_info(self, tokens: List[str]) -> dict[str, list[int]]:
        info_pos = []
        info_time = []
        info_time_bar = []
        info_pitch = []
        info_cof = []

        # Setup Values
        cur_pos = 0
        cur_time = 0
        cur_time_bar = 0
        cur_time_signature_numerator = DEFAULT_TIME_SIGNATURE_NUMERATOR
        cur_time_signature_denominator = DEFAULT_TIME_SIGNATURE_DENOMINATOR
        cur_bar_capacity_total = int(self.ppqn * 4 * cur_time_signature_numerator / cur_time_signature_denominator)
        cur_bar_capacity_remaining = cur_bar_capacity_total

        for token in tokens:
            token_parts = self._split_token(token)
            part_main = token_parts[0][0]

            info_time.append(cur_time)
            info_time_bar.append(cur_time_bar)

            if part_main == TokenisationPrefixes.BAR.value:
                cur_time += cur_bar_capacity_remaining
                cur_time_bar = 0
                cur_bar_capacity_remaining = cur_bar_capacity_total

                info_pitch.append(math.nan)
                info_cof.append(math.nan)
            elif part_main == TokenisationPrefixes.REST.value:
                cur_time += int(token_parts[0][1])
                cur_time_bar += int(token_parts[0][1])
                cur_bar_capacity_remaining -= int(token_parts[0][1])

                info_pitch.append(math.nan)
                info_cof.append(math.nan)
            elif part_main == TokenisationPrefixes.INSTRUMENT.value:
                note_pitch = int(token_parts[1][1])

                info_pitch.append(note_pitch)
                info_cof.append(CircleOfFifths.get_position(note_pitch))
            elif part_main == TokenisationPrefixes.TIME_SIGNATURE.value:
                if cur_time_bar > 0:
                    LOGGER.warning(
                        f"Skipping time signature change mid-bar at time {cur_time} (bar time {cur_time_bar})")
                else:
                    cur_time_signature_numerator = int(token_parts[0][1])
                    cur_time_signature_denominator = int(token_parts[0][2])
                    cur_bar_capacity_total = int(
                        self.ppqn * 4 * cur_time_signature_numerator / cur_time_signature_denominator)
                    cur_bar_capacity_remaining = cur_bar_capacity_total

                info_pitch.append(math.nan)
                info_cof.append(math.nan)
            else:
                info_pitch.append(math.nan)
                info_cof.append(math.nan)

            info_pos.append(cur_pos)
            cur_pos += 1

        return {"info_position": info_pos,
                "info_time": info_time,
                "info_time_bar": info_time_bar,
                "info_pitch": info_pitch,
                "info_circle_of_fifths": info_cof}

    def _split_token(self, token: str):
        parts = token.split("-")
        sub_parts = [part.split("_") for part in parts]
        return sub_parts

    def _construct_dictionary(self):
        self.dictionary[TokenisationPrefixes.PAD.value] = 0
        self.dictionary_size += 1

        self.dictionary[TokenisationPrefixes.START.value] = 1
        self.dictionary_size += 1

        self.dictionary[TokenisationPrefixes.STOP.value] = 2
        self.dictionary_size += 1

        self.dictionary[TokenisationPrefixes.BAR.value] = 3
        self.dictionary_size += 1

        for step_size in self.step_sizes:
            self.dictionary[f"{TokenisationPrefixes.REST.value}_{step_size:02}"] = self.dictionary_size
            self.dictionary_size += 1

        for i_ins in range(self.num_instruments):
            for pitch in range(self.pitch_range[0], self.pitch_range[1] + 1):
                for note_value in self.note_values:
                    for velocity_bin in self.velocity_bins:
                        self.dictionary[(f"{TokenisationPrefixes.INSTRUMENT.value}_{i_ins:02}-"
                                         f"{TokenisationPrefixes.PITCH.value}_{pitch:03}-"
                                         f"{TokenisationPrefixes.VALUE.value}_{note_value:02}-"
                                         f"{TokenisationPrefixes.VELOCITY.value}_{velocity_bin:03}")] = self.dictionary_size
                        self.dictionary_size += 1

        for time_signature in range(self.time_signature_range[0], self.time_signature_range[1] + 1):
            self.dictionary[
                f"{TokenisationPrefixes.TIME_SIGNATURE.value}_{time_signature:02}_{DEFAULT_TIME_SIGNATURE_DENOMINATOR:02}"] = self.dictionary_size
            self.dictionary_size += 1

        self.inverse_dictionary = {v: k for k, v in self.dictionary.items()}

    def _flush_buffer(self, time: int) -> List[str]:
        tokens = []

        if time >= 40:
            pass

        while any(time >= rest for rest in self.step_sizes):
            for rest in reversed(self.step_sizes):
                if time >= rest:
                    tokens.append(f"{TokenisationPrefixes.REST.value}_{rest:02}")
                    time -= rest
                    break

        if time > 0:
            raise TokenisationException(f"Invalid remaining rest value: {time}")

        return tokens


# OLD

class BaseTokeniser(ABC):
    TOKEN_PAD = 0
    TOKEN_START = 1
    TOKEN_STOP = 2
    TOKEN_SEPARATOR = 3
    VOCAB_SIZE = -1

    def __init__(self) -> None:
        super().__init__()

        self.flags = dict()

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
        self.prv_note = None
        self.prv_value = -1
        self.prv_numerator = -1

    def _general_tokenise_flush_time_buffer(self, time: int, index_time_def: int) -> list[int]:
        tokens = []

        while time > self.set_max_rest_value:
            tokens.append(int(self.set_max_rest_value + index_time_def - 1))
            time -= self.set_max_rest_value

        if time > 0:
            tokens.append(int(time + index_time_def - 1))

        return tokens

    def _notelike_tokenise_flush_rest_buffer(self, apply_target: bool, wait_token: int, index_time_def: int) -> list[
        int]:
        tokens = []

        # Insert rests of length up to `set_max_rest_value`
        while self.cur_rest_buffer > self.set_max_rest_value:
            if not (self.prv_value == self.set_max_rest_value and self.flags.get(TokenisationFlags.RUNNING_VALUE,
                                                                                 False)):
                tokens.append(int(self.set_max_rest_value + index_time_def - 1))
                self.prv_value = self.set_max_rest_value

            tokens.append(int(wait_token))
            self.cur_time += self.set_max_rest_value
            self.cur_rest_buffer -= self.set_max_rest_value

        # Insert rests smaller than `set_max_rest_value`
        if self.cur_rest_buffer > 0:
            if not (self.prv_value == self.cur_rest_buffer and self.flags.get(TokenisationFlags.RUNNING_VALUE, False)):
                tokens.append(int(self.cur_rest_buffer + index_time_def - 1))
                self.prv_value = self.cur_rest_buffer
            tokens.append(int(wait_token))

        self.cur_time += self.cur_rest_buffer
        self.cur_rest_buffer = 0

        # If there are open notes, extend the sequence to the minimum needed time target
        if apply_target and self.cur_time_target > self.cur_time:
            self.cur_rest_buffer += self.cur_time_target - self.cur_time
            tokens.extend(
                self._notelike_tokenise_flush_rest_buffer(apply_target=False, wait_token=wait_token,
                                                          index_time_def=index_time_def))

        return tokens

    def _gridlike_tokenise_flush_grid_buffer(self, min_grid_size: int, wait_token: int) -> list[int]:
        tokens = []

        while self.cur_rest_buffer > 0:
            tokens.append(wait_token)
            self.cur_rest_buffer -= min_grid_size

        return tokens

    @abstractmethod
    def tokenise(self, sequence: Sequence, insert_trailing_separator_token: bool = True,
                 insert_border_tokens: bool = False) -> list[int]:
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


class BaseNotelikeTokeniser(BaseTokeniser, ABC):

    def __init__(self, running_value: bool, running_time_sig: bool) -> None:
        super().__init__()

        self.flags[TokenisationFlags.RUNNING_VALUE] = running_value
        self.flags[TokenisationFlags.RUNNING_TIME_SIG] = running_time_sig


class BaseLargeVocabularyNotelikeTokeniser(BaseNotelikeTokeniser, ABC):
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
                    raise TokenisationException(f"Invalid note pitch: {msg_note}")
                if msg_value not in LargeVocabularyNotelikeTokeniser.SUPPORTED_VALUES:
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


class LargeVocabularyNotelikeTokeniser(BaseLargeVocabularyNotelikeTokeniser):
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

    VOCAB_SIZE = 1451

    def __init__(self, running_time_sig: bool) -> None:
        super().__init__(running_time_sig)

    NOTE_SECTION_SIZE = 88

    def _tokenise_note(self, tokens: list[int], msg_note: int, msg_value: int) -> None:
        # Add token representing pitch and value
        tokens.append(
            msg_note - 21 + 28 + LargeVocabularyNotelikeTokeniser.SUPPORTED_VALUES.index(msg_value) * 88)

    @staticmethod
    def detokenise(tokens: list[int]) -> Sequence:
        seq = Sequence()
        cur_time = 0

        note_section_size = LargeVocabularyNotelikeTokeniser.NOTE_SECTION_SIZE
        boundary_token_ts = len(LargeVocabularyNotelikeTokeniser.SUPPORTED_VALUES) * note_section_size + 4 + 24

        for token in tokens:
            if token <= 3:
                pass
            elif 4 <= token <= 27:
                cur_time += token - 3
            elif 28 <= token <= boundary_token_ts - 1:
                note_pitch = (token - 28) % note_section_size + 21
                note_value = LargeVocabularyNotelikeTokeniser.SUPPORTED_VALUES[(token - 28) // note_section_size]

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

    @staticmethod
    def get_info(tokens: list[int]) -> dict():
        info_pos = []
        info_time = []
        info_time_bar = []
        info_pitch = []
        info_cof = []

        cur_pos = 0
        cur_time = 0
        cur_time_bar = 0
        note_section_size = LargeVocabularyNotelikeTokeniser.NOTE_SECTION_SIZE
        boundary_token_ts = len(LargeVocabularyNotelikeTokeniser.SUPPORTED_VALUES) * note_section_size + 4 + 24

        for token in tokens:
            info_time.append(cur_time)
            info_time_bar.append(cur_time_bar)

            if token <= 2:
                info_pitch.append(math.nan)
                info_cof.append(math.nan)
            elif token == 3:
                info_pitch.append(math.nan)
                info_cof.append(math.nan)
                cur_time_bar = 0
            elif 4 <= token <= 27:
                cur_time += token - 3
                cur_time_bar += token - 3

                info_pitch.append(math.nan)
                info_cof.append(math.nan)
            elif 28 <= token <= boundary_token_ts - 1:
                note_pitch = (token - 28) % note_section_size + 21
                # note_value = LargeVocabularyNotelikeTokeniser.SUPPORTED_VALUES[(token - 28) // note_section_size]

                assert 21 <= note_pitch <= 108, f"Invalid note pitch: {note_pitch}"

                info_pitch.append(note_pitch - 21)
                info_cof.append(CircleOfFifths.get_position(note_pitch))
            elif boundary_token_ts <= token <= boundary_token_ts + 14:
                info_pitch.append(math.nan)
                info_cof.append(math.nan)
            else:
                raise TokenisationException(f"Encountered invalid token during detokenisation: {token}")

            info_pos.append(cur_pos)

            cur_pos += 1

        return {"info_position": info_pos,
                "info_time": info_time,
                "info_time_bar": info_time_bar,
                "info_pitch": info_pitch,
                "info_circle_of_fifths": info_cof}

    @staticmethod
    def get_mask(tokens: list[int], max_len: int = -1, previous_state: dict = None) -> tuple[
        list[np.ndarray], dict[str, Any]]:
        cur_step = 0
        cur_time = 0
        cur_bar_capacity_overall = 0
        cur_bar_capacity_remaining = 0
        cur_numerator = 8

        flag_seq_started = False
        flag_seq_stopped = False
        flag_at_bar_start = False
        flag_at_bar_end = False
        mem_cur_step_notes = dict()

        note_section_size = LargeVocabularyNotelikeTokeniser.NOTE_SECTION_SIZE
        boundary_token_ts = len(LargeVocabularyNotelikeTokeniser.SUPPORTED_VALUES) * note_section_size + 4 + 24

        if previous_state is not None:
            cur_step = previous_state.get("prv_step", cur_step)
            cur_time = previous_state.get("prv_time", cur_time)
            cur_bar_capacity_overall = previous_state.get("prv_bar_capacity_overall", cur_bar_capacity_overall)
            cur_bar_capacity_remaining = previous_state.get("prv_bar_capacity_remaining", cur_bar_capacity_remaining)
            cur_numerator = previous_state.get("prv_numerator", cur_numerator)

            flag_seq_started = previous_state.get("prv_flag_seq_started", flag_seq_started)
            flag_seq_stopped = previous_state.get("prv_flag_seq_stopped", flag_seq_stopped)
            flag_at_bar_start = previous_state.get("prv_flag_at_bar_start", flag_at_bar_start)
            flag_at_bar_end = previous_state.get("prv_flag_at_bar_end", flag_at_bar_end)
            mem_cur_step_notes = previous_state.get("prv_mem_cur_step_notes", mem_cur_step_notes)

        masks = []

        for i_token, token in enumerate(tokens[cur_step:]):
            if max_len != -1 and i_token >= max_len:
                break

            # Reconnaissance
            if token == 0:
                pass
            elif token == 1:
                flag_seq_started = True
                flag_at_bar_start = True

                cur_bar_capacity_remaining = 12 * cur_numerator
                cur_bar_capacity_overall = cur_bar_capacity_remaining
            elif token == 2:
                flag_seq_stopped = True
            elif token == 3:
                flag_at_bar_start = True
                flag_at_bar_end = False

                cur_bar_capacity_remaining = cur_numerator * 12
                cur_bar_capacity_overall = cur_bar_capacity_remaining
            elif 4 <= token <= 27:
                cur_time += token - 3
                cur_bar_capacity_remaining -= token - 3
                flag_at_bar_start = False

                new_mem_cur_step_notes = dict()
                for note_end_time, note_pitches in mem_cur_step_notes.items():
                    if note_end_time > cur_time:
                        new_mem_cur_step_notes[note_end_time] = note_pitches
                mem_cur_step_notes = new_mem_cur_step_notes

                if cur_bar_capacity_remaining < 0:
                    raise TokenisationException("Bar capacity underflow while calculating restraints.")

                if cur_bar_capacity_remaining == 0:
                    flag_at_bar_end = True
            elif 28 <= token <= boundary_token_ts - 1:
                note_pitch = (token - 28) % note_section_size + 21
                note_value = LargeVocabularyNotelikeTokeniser.SUPPORTED_VALUES[(token - 28) // note_section_size]

                flag_at_bar_start = False
                mem_cur_step_notes.setdefault(cur_time + note_value, set()).add(note_pitch)

                if note_value > cur_bar_capacity_remaining:
                    raise TokenisationException("Note value exceeds bar capacity while calculating restraints.")

            elif boundary_token_ts <= token <= boundary_token_ts + 14:
                if not flag_at_bar_start:
                    raise TokenisationException("Time signature not at bar start while calculating restraints.")
                flag_at_bar_start = False

                cur_numerator = token - boundary_token_ts + 2
                cur_bar_capacity_remaining = cur_numerator * 12
                cur_bar_capacity_overall = cur_bar_capacity_remaining
            else:
                raise TokenisationException(f"Encountered invalid token during restraints calculation: {token}")

            # Masking, one means allowed
            mask = np.ones(LargeVocabularyNotelikeTokeniser.VOCAB_SIZE, dtype=bool)

            if not flag_seq_started:
                # If sequence not started only start token allowed
                mask = np.zeros(LargeVocabularyNotelikeTokeniser.VOCAB_SIZE, dtype=bool)
                mask[2] = 1
            else:
                # Sequences has started, padding and start token disallowed
                mask[0] = 0
                mask[1] = 0

                if flag_seq_stopped:
                    # If sequence stopped only padding token allowed
                    mask = np.zeros(LargeVocabularyNotelikeTokeniser.VOCAB_SIZE, dtype=bool)
                    mask[0] = 1
                else:
                    if not flag_at_bar_start:
                        # Mask time signature messages
                        mask[boundary_token_ts:boundary_token_ts + 14 + 1] = 0
                    if not flag_at_bar_end:
                        # Mask end token
                        mask[2] = 0
                        # Mask separator token
                        mask[3] = 0

                    if cur_bar_capacity_remaining < 24:
                        # Mask wait tokens
                        mask[4 + cur_bar_capacity_remaining:27 + 1] = 0

                    for i, supported_value in enumerate(LargeVocabularyNotelikeTokeniser.SUPPORTED_VALUES):
                        # Mask notes with duration exceeding bar capacity
                        if supported_value > cur_bar_capacity_remaining:
                            mask[28 + note_section_size * i:28 + note_section_size * (i + 1)] = 0

                    for note_end_time, note_pitches in mem_cur_step_notes.items():
                        for note_pitch in note_pitches:
                            for i, supported_value in enumerate(LargeVocabularyNotelikeTokeniser.SUPPORTED_VALUES):
                                # Mask notes that are still active
                                helper = 28 + note_pitch - 21 + note_section_size * i
                                mask[28 + note_pitch - 21 + note_section_size * i] = 0

            cur_step += 1
            masks.append(mask)

        return masks, {"prv_step": cur_step,
                       "prv_time": cur_time,
                       "prv_bar_capacity_overall": cur_bar_capacity_overall,
                       "prv_bar_capacity_remaining": cur_bar_capacity_remaining,
                       "prv_numerator": cur_numerator,
                       "prv_flag_seq_started": flag_seq_started,
                       "prv_flag_seq_stopped": flag_seq_stopped,
                       "prv_flag_at_bar_start": flag_at_bar_start,
                       "prv_flag_at_bar_end": flag_at_bar_end,
                       "prv_mem_cur_step_notes": mem_cur_step_notes}
