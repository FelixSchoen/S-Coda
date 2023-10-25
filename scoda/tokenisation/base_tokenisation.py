from abc import ABC, abstractmethod

from scoda.exceptions.tokenisation_exception import TokenisationException
from scoda.sequences.sequence import Sequence
from scoda.settings.settings import PPQN
from scoda.utils.enumerations import Flags


class BaseTokeniser(ABC):

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
        self.prv_note = None
        self.prv_value = -1
        self.prv_numerator = -1

    def _general_tokenise_flush_time_buffer(self, time: int, value_shift: int) -> list[int]:
        tokens = []

        while time > self.set_max_rest_value:
            tokens.append(int(self.set_max_rest_value + value_shift))
            time -= self.set_max_rest_value

        if time > 0:
            tokens.append(int(time + value_shift))

        return tokens

    def _notelike_tokenise_flush_rest_buffer(self, apply_target: bool, wait_token: int, value_shift: int) -> list[int]:
        tokens = []

        # Insert rests of length up to `set_max_rest_value`
        while self.cur_rest_buffer > self.set_max_rest_value:
            if not (self.prv_value == self.set_max_rest_value and self.flags.get(Flags.RUNNING_VALUE, False)):
                tokens.append(int(self.set_max_rest_value + value_shift))
                self.prv_value = self.set_max_rest_value

            tokens.append(int(wait_token))
            self.cur_time += self.set_max_rest_value
            self.cur_rest_buffer -= self.set_max_rest_value

        # Insert rests smaller than `set_max_rest_value`
        if self.cur_rest_buffer > 0:
            if not (self.prv_value == self.cur_rest_buffer and self.flags.get(Flags.RUNNING_VALUE, False)):
                tokens.append(int(self.cur_rest_buffer + value_shift))
                self.prv_value = self.cur_rest_buffer
            tokens.append(int(wait_token))

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
