from abc import ABC, abstractmethod

from scoda.exceptions.tokenisation_exception import TokenisationException
from scoda.sequences.sequence import Sequence
from scoda.settings.settings import PPQN
from scoda.utils.enumerations import MessageType, Flags


class Tokeniser(ABC):

    def __init__(self, running_value: bool, running_time_sig: bool) -> None:
        super().__init__()

        self.buffer_tokens = None
        self.buffer_sequence = None

        self.flags = dict()
        self.flags[Flags.RUNNING_VALUE] = running_value
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
        self.buffer_tokens = []
        self.buffer_sequence = Sequence()

        self.cur_time = 0
        self.cur_time_target = 0
        self.cur_rest_buffer = 0

        self.prv_type = None
        self.prv_value = -1
        self.prv_numerator = -1

    @abstractmethod
    def tokenise(self, sequence: Sequence):
        pass

    @abstractmethod
    def detokenise(self):
        pass

    @staticmethod
    def _time_signature_to_eights(numerator: int, denominator: int) -> int:
        scaled = numerator * (8 / denominator)

        if (not float(scaled).is_integer()) or (not scaled >= 2):
            raise TokenisationException(
                f"Original time signature of {int(numerator)}/{int(denominator)} cannot be represented as multiples of eights")

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
        super().__init__(running_value, running_time_sig)

    def tokenise(self, sequence: Sequence):
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
                    tokens.extend(self.tokenise_flush_rest_buffer())

                # Check if value of note has to be defined
                if not (self.prv_value == msg_value and self.flags.get(Flags.RUNNING_VALUE, False)):
                    tokens.extend(self.tokenise_flush_generic_buffer(msg_value))

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
                    tokens.extend(self.tokenise_flush_rest_buffer())
                    tokens.append(numerator - 2 + 116)

                self.prv_type = MessageType.TIME_SIGNATURE
                self.prv_numerator = numerator
            elif msg_type == MessageType.INTERNAL:
                self.cur_rest_buffer += msg_time
                self.prv_type = MessageType.INTERNAL

        return tokens

    def tokenise_flush_rest_buffer(self, apply_target: bool = False) -> list[int]:
        tokens = []

        # Insert rests of length up to `set_max_rest_value`
        while self.cur_rest_buffer > self.set_max_rest_value:
            if not (self.prv_value == self.set_max_rest_value and self.flags.get(Flags.RUNNING_VALUE, False)):
                tokens.append(self.set_max_rest_value)
                self.prv_value = self.set_max_rest_value

            tokens.append(3)
            self.cur_time += self.set_max_rest_value
            self.cur_rest_buffer -= self.set_max_rest_value

        # Insert rests smaller than `set_max_rest_value`
        if self.cur_rest_buffer > 0:
            if not (self.prv_value == self.cur_rest_buffer and self.flags.get(Flags.RUNNING_VALUE, False)):
                tokens.append(self.cur_rest_buffer)
                self.prv_value = self.cur_rest_buffer
            tokens.append(3)

        self.cur_time += self.cur_rest_buffer
        self.cur_rest_buffer = 0

        # If there are open notes, extend the sequence to the minimum needed time target
        if apply_target and self.cur_time_target > self.cur_time:
            self.cur_rest_buffer += self.cur_time_target - self.cur_time
            tokens.extend(self.tokenise_flush_rest_buffer(apply_target=False))

        return tokens

    def tokenise_flush_generic_buffer(self, time: int) -> list[int]:
        tokens = []
        while time > self.set_max_rest_value:
            tokens.append(self.set_max_rest_value + 3)
            time -= self.set_max_rest_value
        if time > 0:
            tokens.append(time + 3)

        return tokens

    def detokenise(self):
        pass
