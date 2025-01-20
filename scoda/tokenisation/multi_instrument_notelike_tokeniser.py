import math
from abc import ABC, abstractmethod
from tokenize import Token
from typing import Any, Tuple, List

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
from scoda.settings.settings import PPQN
from scoda.tokenisation.base_tokenisation import BaseTokeniser

LOGGER = get_logger(__name__)


class MultiInstrumentLDNotelikeTokeniser:

    def __init__(self,
                 ppqn: int = None,
                 num_instruments: int = 1,
                 pitch_range: Tuple[int, int] = (21, 108),
                 step_sizes: list[int] = None,
                 note_values: list[int] = None,
                 velocity_bins: int = 1,
                 time_signature_range: Tuple[int, int] = (2, 16)):
        self.dictionary = dict()
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
            self.step_sizes = get_default_step_sizes()
        self.step_sizes.sort()
        if self.note_values is None:
            self.note_values = get_default_note_values()
        self.note_values.sort()

        self.velocity_bins = get_velocity_bins(velocity_bins=velocity_bins)

        # Memory
        self.cur_time = None
        self.cur_time_target = None
        self.cur_rest_buffer = None

        self.prv_type = None
        self.prv_note = None
        self.prv_value = None
        self.prv_numerator = None

        # Construct dictionary
        self.construct_dictionary()

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

    def construct_dictionary(self):
        self.dictionary[TokenisationPrefixes.PAD.value] = 0
        self.dictionary_size += 1

        self.dictionary[TokenisationPrefixes.START.value] = 1
        self.dictionary_size += 1

        self.dictionary[TokenisationPrefixes.STOP.value] = 2
        self.dictionary_size += 1

        self.dictionary[TokenisationPrefixes.BAR.value] = 3

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
                f"{TokenisationPrefixes.TIME_SIGNATURE.value}_{time_signature:02}_08"] = self.dictionary_size
            self.dictionary_size += 1

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

                scaled = msg_numerator * (8 / msg_denominator)
                if not float(scaled).is_integer():
                    raise TokenisationException(
                        f"Time signature {int(msg_numerator)}/{int(msg_denominator)} cannot be represented as multiples of eights")
                scaled = int(scaled)
                if not self.time_signature_range[0] <= scaled <= self.time_signature_range[1]:
                    raise TokenisationException(f"Invalid time signature numerator: {scaled}")

                tokens.append(f"{TokenisationPrefixes.TIME_SIGNATURE.value}_{scaled:02}_08")

        if insert_bar_token:
            tokens.append(TokenisationPrefixes.BAR.value)

        if reset_time:
            self.reset_time()

        return tokens

    def detokenise(self):
        pass

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
