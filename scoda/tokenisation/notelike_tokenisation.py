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
                 num_tracks: int = 1,
                 pitch_range: Tuple[int, int] = (21, 108),
                 step_sizes: list[int] = None,
                 note_values: list[int] = None,
                 velocity_bins: int = 1,
                 time_signature_range: Tuple[int, int] = (2, 16),
                 flag_running_time_signature: bool = True,
                 flag_simplify_time_signature: bool = True):
        self.dictionary = dict()
        self.inverse_dictionary = dict()
        self.dictionary_size = 0

        self.ppqn = ppqn
        self.step_sizes = step_sizes
        self.note_values = note_values
        self.num_tracks = num_tracks
        self.pitch_range = pitch_range
        self.time_signature_range = time_signature_range

        self.flag_running_time_signature = flag_running_time_signature
        self.flag_simplify_time_signature = flag_simplify_time_signature

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

    def tokenise(self,
                 sequences_bar: list[Sequence],
                 insert_bar_token: bool = True,
                 reset_time: bool = True) -> List[str]:
        tokens = []

        assert len(sequences_bar) == self.num_tracks

        # Merge sequences
        for i, sequence_bar in enumerate(sequences_bar):
            sequence_bar.set_channel(i)
        sequence_bar = Sequence()
        sequence_bar.merge(sequences_bar)

        interleaved_pairings = sequence_bar.get_interleaved_message_pairings(
            [MessageType.NOTE_ON, MessageType.NOTE_OFF, MessageType.TIME_SIGNATURE, MessageType.INTERNAL])

        for interleaved_pairing in interleaved_pairings:
            event_pairing = interleaved_pairing[1]

            msg_channel = interleaved_pairing[0]
            assert msg_channel == event_pairing[0].channel

            msg_type = event_pairing[0].message_type
            msg_time = event_pairing[0].time

            # Check if message occurs at current time, if not place rest messages
            if not self.cur_time == msg_time:
                tokens.extend(self._flush_buffer(msg_time - self.cur_time))
                self.cur_time = msg_time
                self.cur_rest_buffer = 0

            if msg_type == MessageType.NOTE_ON:
                msg_channel = event_pairing[0].channel
                msg_note = event_pairing[0].note
                msg_value = event_pairing[1].time - msg_time
                msg_velocity = self.velocity_bins[bin_velocity(event_pairing[0].velocity, self.velocity_bins)]

                if not (self.pitch_range[0] <= msg_note <= self.pitch_range[1]):
                    raise TokenisationException(f"Invalid note pitch: {msg_note}")
                if msg_value not in self.note_values:
                    raise TokenisationException(f"Invalid note value: {msg_value}")

                tokens.append(f"{TokenisationPrefixes.TRACK.value}_{msg_channel:02}-"
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

    def detokenise(self,
                   tokens: List[str]) -> List[Sequence]:
        # Setup Values
        sequences = [Sequence() for _ in range(self.num_tracks)]
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
            elif part_main == TokenisationPrefixes.TRACK.value:
                note_track = int(token_parts[0][1])
                note_pitch = int(token_parts[1][1])
                note_value = int(token_parts[2][1])
                note_velocity = int(token_parts[3][1])

                sequences[note_track].add_absolute_message(
                    Message(message_type=MessageType.NOTE_ON, note=note_pitch, time=cur_time, velocity=note_velocity)
                )
                sequences[note_track].add_absolute_message(
                    Message(message_type=MessageType.NOTE_OFF, note=note_pitch, time=cur_time + note_value)
                )
            elif part_main == TokenisationPrefixes.TIME_SIGNATURE.value:
                if cur_time_bar > 0:
                    LOGGER.warning(
                        f"Skipping time signature change mid-bar at time {cur_time} (bar time {cur_time_bar})")
                else:
                    switched = False

                    new_time_signature_numerator = int(token_parts[0][1])
                    new_time_signature_denominator = int(token_parts[0][2])

                    if cur_time_signature_numerator != new_time_signature_numerator or \
                            cur_time_signature_denominator != new_time_signature_denominator:
                        switched = True

                    cur_time_signature_numerator = new_time_signature_numerator
                    cur_time_signature_denominator = new_time_signature_denominator
                    cur_bar_capacity_total = int(
                        self.ppqn * 4 * cur_time_signature_numerator / cur_time_signature_denominator)
                    cur_bar_capacity_remaining = cur_bar_capacity_total

                    if self.flag_simplify_time_signature and \
                            cur_time_signature_numerator % 2 == 0 and \
                            cur_time_signature_denominator % 2 == 0:
                        cur_time_signature_numerator = int(cur_time_signature_numerator / 2)
                        cur_time_signature_denominator = int(cur_time_signature_denominator / 2)

                    if switched or not self.flag_running_time_signature:
                        sequences[0].add_absolute_message(
                            Message(message_type=MessageType.TIME_SIGNATURE,
                                    time=cur_time,
                                    numerator=cur_time_signature_numerator,
                                    denominator=cur_time_signature_denominator)
                        )
            else:
                raise TokenisationException(f"Invalid token: {token}")

        return sequences

    def encode(self,
               tokens: List[str]) -> List[int]:
        return [self.dictionary[token] for token in tokens]

    def decode(self,
               tokens: List[int]) -> List[str]:
        return [self.inverse_dictionary[token] for token in tokens]

    def get_info(self,
                 tokens: List[str],
                 flag_impute_values: bool = False) -> dict[str, list[int]]:
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
        prv_pitch = 69  # Concert pitch A4

        for token in tokens:
            token_parts = self._split_token(token)
            part_main = token_parts[0][0]

            info_time.append(cur_time)
            info_time_bar.append(cur_time_bar)

            if part_main == TokenisationPrefixes.BAR.value:
                cur_time += cur_bar_capacity_remaining
                cur_time_bar = 0
                cur_bar_capacity_remaining = cur_bar_capacity_total

                if not flag_impute_values:
                    info_pitch.append(math.nan)
                    info_cof.append(math.nan)
                else:
                    info_pitch.append(prv_pitch)
                    info_cof.append(CircleOfFifths.get_position(prv_pitch))
            elif part_main == TokenisationPrefixes.REST.value:
                cur_time += int(token_parts[0][1])
                cur_time_bar += int(token_parts[0][1])
                cur_bar_capacity_remaining -= int(token_parts[0][1])

                if not flag_impute_values:
                    info_pitch.append(math.nan)
                    info_cof.append(math.nan)
                else:
                    info_pitch.append(prv_pitch)
                    info_cof.append(CircleOfFifths.get_position(prv_pitch))
            elif part_main == TokenisationPrefixes.TRACK.value:
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

                if not flag_impute_values:
                    info_pitch.append(math.nan)
                    info_cof.append(math.nan)
                else:
                    info_pitch.append(prv_pitch)
                    info_cof.append(CircleOfFifths.get_position(prv_pitch))
            else:
                if not flag_impute_values:
                    info_pitch.append(math.nan)
                    info_cof.append(math.nan)
                else:
                    info_pitch.append(prv_pitch)
                    info_cof.append(CircleOfFifths.get_position(prv_pitch))

            info_pos.append(cur_pos)
            cur_pos += 1

        return {"info_position": info_pos,
                "info_time": info_time,
                "info_time_bar": info_time_bar,
                "info_pitch": info_pitch,
                "info_circle_of_fifths": info_cof}

    def _split_token(self,
                     token: str):
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

        for i_ins in range(self.num_tracks):
            for pitch in range(self.pitch_range[0], self.pitch_range[1] + 1):
                for note_value in self.note_values:
                    for velocity_bin in self.velocity_bins:
                        self.dictionary[(f"{TokenisationPrefixes.TRACK.value}_{i_ins:02}-"
                                         f"{TokenisationPrefixes.PITCH.value}_{pitch:03}-"
                                         f"{TokenisationPrefixes.VALUE.value}_{note_value:02}-"
                                         f"{TokenisationPrefixes.VELOCITY.value}_{velocity_bin:03}")] = self.dictionary_size
                        self.dictionary_size += 1

        for time_signature in range(self.time_signature_range[0], self.time_signature_range[1] + 1):
            self.dictionary[
                f"{TokenisationPrefixes.TIME_SIGNATURE.value}_{time_signature:02}_{DEFAULT_TIME_SIGNATURE_DENOMINATOR:02}"] = self.dictionary_size
            self.dictionary_size += 1

        self.inverse_dictionary = {v: k for k, v in self.dictionary.items()}

    def _flush_buffer(self,
                      time: int) -> List[str]:
        tokens = []

        while any(time >= rest for rest in self.step_sizes):
            for rest in reversed(self.step_sizes):
                if time >= rest:
                    tokens.append(f"{TokenisationPrefixes.REST.value}_{rest:02}")
                    time -= rest
                    break

        if time > 0:
            raise TokenisationException(f"Invalid remaining rest value: {time}")

        return tokens
