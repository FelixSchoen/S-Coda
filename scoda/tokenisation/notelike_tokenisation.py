import itertools
import math
from typing import Tuple, List

from scoda.elements.message import Message
from scoda.enumerations.message_type import MessageType
from scoda.enumerations.tokenisation_prefixes import TokenisationPrefixes
from scoda.exceptions.tokenisation_exception import TokenisationException
from scoda.misc.music_theory import CircleOfFifths
from scoda.misc.scoda_logging import get_logger
from scoda.misc.util import get_default_step_sizes, get_default_note_values, get_velocity_bins, bin_velocity
from scoda.sequences.sequence import Sequence
from scoda.settings.settings import PPQN, DEFAULT_TIME_SIGNATURE_NUMERATOR, DEFAULT_TIME_SIGNATURE_DENOMINATOR

LOGGER = get_logger(__name__)


class MultiTrackLargeVocabularyNotelikeTokeniser:
    sort_order = [TokenisationPrefixes.TRACK.value, TokenisationPrefixes.VALUE.value,
                  TokenisationPrefixes.VELOCITY.value, TokenisationPrefixes.PITCH.value]

    def __init__(self,
                 ppqn: int = None,
                 num_tracks: int = 1,
                 pitch_range: Tuple[int, int] = (21, 108),
                 step_sizes: list[int] = None,
                 note_values: list[int] = None,
                 velocity_bins: int = 1,
                 time_signature_range: Tuple[int, int] = (2, 16),
                 bar_position_quarters_range: float = 4.0,
                 flag_absolute_bar_position: bool = False,
                 flag_running_values: bool = True,
                 flag_running_time_signature: bool = True,
                 flag_bar_token: bool = True,
                 flag_fuse_track: bool = True,
                 flag_fuse_value: bool = True,
                 flag_fuse_velocity: bool = True,
                 flag_simplify_time_signature: bool = True):
        self.dictionary = dict()
        self.inverse_dictionary = dict()
        self._dictionary_size = 0

        self.ppqn = ppqn
        self.step_sizes = step_sizes
        self.note_values = note_values
        self.num_tracks = num_tracks
        self.pitch_range = pitch_range
        self.time_signature_range = time_signature_range
        self.bar_position_quarters_range = bar_position_quarters_range

        self.flag_absolute_bar_position = flag_absolute_bar_position
        self.flag_running_values = flag_running_values
        self.flag_running_time_signature = flag_running_time_signature
        self.flag_bar_token = flag_bar_token
        self.flag_fuse_track = flag_fuse_track
        self.flag_fuse_value = flag_fuse_value
        self.flag_fuse_velocity = flag_fuse_velocity
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

        if not self.flag_running_time_signature:
            raise NotImplementedError()

        if self.flag_absolute_bar_position and not self.flag_bar_token:
            raise TokenisationException("Absolute bar position requires bar token")

    @property
    def dictionary_size(self):
        return self._dictionary_size

    def tokenise(self,
                 sequences_bar: list[Sequence],
                 state_dict: dict = None) -> List[str]:
        if state_dict is None:
            state_dict = dict()

        # Setup Values
        tokens = []
        cur_time = state_dict.get("cur_time", 0)
        cur_time_bar = state_dict.get("cur_time_bar", 0)
        cur_time_signature_numerator = state_dict.get("cur_time_signature_numerator",
                                                      DEFAULT_TIME_SIGNATURE_NUMERATOR)
        cur_time_signature_denominator = state_dict.get("cur_time_signature_denominator",
                                                        DEFAULT_TIME_SIGNATURE_DENOMINATOR)
        cur_bar_capacity_total = int(self.ppqn * 4 * cur_time_signature_numerator / cur_time_signature_denominator)
        cur_bar_capacity_remaining = state_dict.get("cur_bar_capacity_remaining", cur_bar_capacity_total)
        prv_track = state_dict.get("prv_track", -1)
        prv_value = state_dict.get("prv_value", -1)
        prv_velocity = state_dict.get("prv_velocity", -1)
        prv_shift = state_dict.get("cur_time", 0)

        # Sanity check
        if not len(sequences_bar) == self.num_tracks:
            raise TokenisationException("Number of sequences does not match number of tracks")

        # Utility function
        def _apply_rest(rest: int):
            nonlocal tokens
            nonlocal cur_time
            nonlocal cur_time_bar
            nonlocal cur_bar_capacity_remaining
            buf_rest = rest
            pass

            # While rest buffer not empty
            while buf_rest > 0:
                if not self.flag_absolute_bar_position:
                    nxt_rest = min(buf_rest, cur_bar_capacity_remaining)

                    # Check if next rest value is valid
                    if not (nxt_rest > self.step_sizes[-1] or any(nxt_rest >= step_size for step_size in self.step_sizes)):
                        raise TokenisationException(f"Invalid remaining rest value: {nxt_rest}")

                    # Check if next rest value is larger than the largest step size
                    if nxt_rest > self.step_sizes[-1]:
                        rest_value = self.step_sizes[-1]
                    else:
                        rest_value = next(step_size for step_size in reversed(self.step_sizes) if nxt_rest >= step_size)

                    # Apply rest
                    cur_time += rest_value
                    cur_time_bar += rest_value
                    cur_bar_capacity_remaining -= rest_value
                    buf_rest -= rest_value
                    tokens.append(f"{TokenisationPrefixes.REST.value}_{rest_value:02}")

                    # Check if we are at bar end
                    if cur_bar_capacity_remaining == 0:
                        if self.flag_bar_token:
                            tokens.append(TokenisationPrefixes.BAR.value)
                        cur_time_bar = 0
                        cur_bar_capacity_remaining = cur_bar_capacity_total
                else:
                    if buf_rest >= cur_bar_capacity_remaining:
                        cur_time += cur_bar_capacity_remaining
                        cur_time_bar = 0
                        buf_rest -= cur_bar_capacity_remaining
                        cur_bar_capacity_remaining = cur_bar_capacity_total
                        tokens.append(TokenisationPrefixes.BAR.value)
                    else:
                        if cur_time_bar + buf_rest > self.bar_position_quarters_range * self.ppqn:
                            raise TokenisationException(f"Invalid bar position value: {cur_time_bar + buf_rest}")

                        cur_time += buf_rest
                        cur_time_bar += buf_rest
                        cur_bar_capacity_remaining -= buf_rest
                        buf_rest = 0
                        tokens.append(f"{TokenisationPrefixes.POSITION.value}_{cur_time_bar:03}")


        # Merge sequences
        for i, sequence_bar in enumerate(sequences_bar):
            sequence_bar.set_channel(i)
        sequence_bar = Sequence()
        sequence_bar.merge(sequences_bar)

        # Get interleaved pairings
        interleaved_pairings = sequence_bar.get_interleaved_message_pairings(
            [MessageType.NOTE_ON, MessageType.NOTE_OFF, MessageType.TIME_SIGNATURE, MessageType.INTERNAL])

        # Handle pairings
        for interleaved_pairing in interleaved_pairings:
            event_pairing = interleaved_pairing[1]

            msg_channel = interleaved_pairing[0]
            if not msg_channel == event_pairing[0].channel:
                raise TokenisationException("Channel mismatch")

            msg_type = event_pairing[0].message_type
            msg_time = event_pairing[0].time + prv_shift

            # Check if message occurs at current time, if not place rest messages
            if not cur_time == msg_time:
                _apply_rest(msg_time - cur_time)

            # Handle notes
            if msg_type == MessageType.NOTE_ON:
                msg_channel = event_pairing[0].channel
                msg_note = event_pairing[0].note
                msg_value = event_pairing[1].time - event_pairing[0].time
                msg_velocity = self.velocity_bins[bin_velocity(event_pairing[0].velocity, self.velocity_bins)]

                if not (self.pitch_range[0] <= msg_note <= self.pitch_range[1]):
                    raise TokenisationException(f"Invalid note pitch: {msg_note}")
                if msg_value not in self.note_values:
                    raise TokenisationException(f"Invalid note value: {msg_value}")

                token = ""

                if not self.flag_fuse_track and (msg_channel != prv_track or not self.flag_running_values):
                    tokens.append(f"{TokenisationPrefixes.TRACK.value}_{msg_channel:02}")
                elif self.flag_fuse_track:
                    token += f"{TokenisationPrefixes.TRACK.value}_{msg_channel:02}-"

                token += f"{TokenisationPrefixes.PITCH.value}_{msg_note:03}-"

                if not self.flag_fuse_value and (msg_value != prv_value or not self.flag_running_values):
                    tokens.append(f"{TokenisationPrefixes.VALUE.value}_{msg_value:02}")
                elif self.flag_fuse_value:
                    token += f"{TokenisationPrefixes.VALUE.value}_{msg_value:02}-"

                if not self.flag_fuse_velocity and (msg_velocity != prv_velocity or not self.flag_running_values):
                    tokens.append(f"{TokenisationPrefixes.VELOCITY.value}_{msg_velocity:03}")
                elif self.flag_fuse_velocity:
                    token += f"{TokenisationPrefixes.VELOCITY.value}_{msg_velocity:03}-"

                token = token[:-1]
                tokens.append(token)

                prv_track = msg_channel
                prv_value = msg_value
                prv_velocity = msg_velocity
            # Handle time signatures
            elif msg_type == MessageType.TIME_SIGNATURE:
                if cur_time_bar > 0:
                    LOGGER.info(
                        f"Skipping time signature change mid-bar at time {cur_time} (bar time {cur_time_bar})")
                    continue

                msg_numerator = event_pairing[0].numerator
                msg_denominator = event_pairing[0].denominator

                scaled = msg_numerator * (DEFAULT_TIME_SIGNATURE_DENOMINATOR / msg_denominator)
                if not float(scaled).is_integer():
                    raise TokenisationException(
                        f"Time signature {int(msg_numerator)}/{int(msg_denominator)} cannot be represented as multiples of eights")
                scaled = int(scaled)
                if not self.time_signature_range[0] <= scaled <= self.time_signature_range[1]:
                    raise TokenisationException(f"Invalid time signature numerator: {scaled}")

                cur_time_signature_numerator = msg_numerator
                cur_time_signature_denominator = msg_denominator
                cur_bar_capacity_total = int(
                    self.ppqn * 4 * cur_time_signature_numerator / cur_time_signature_denominator)
                cur_bar_capacity_remaining = cur_bar_capacity_total

                tokens.append(
                    f"{TokenisationPrefixes.TIME_SIGNATURE.value}_{scaled:02}_{DEFAULT_TIME_SIGNATURE_NUMERATOR:02}")

        # Close bar and handle rest buffer
        if cur_time_bar > 0 and cur_bar_capacity_remaining > 0:
            _apply_rest(cur_bar_capacity_remaining)

        # Update state dictionary
        state_dict["cur_time"] = cur_time
        state_dict["cur_time_bar"] = cur_time_bar
        state_dict["cur_time_signature_numerator"] = cur_time_signature_numerator
        state_dict["cur_time_signature_denominator"] = cur_time_signature_denominator
        state_dict["cur_bar_capacity_remaining"] = cur_bar_capacity_remaining
        state_dict["prv_track"] = prv_track
        state_dict["prv_value"] = prv_value
        state_dict["prv_velocity"] = prv_velocity

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
        prv_track = 0
        prv_value = 24
        prv_velocity = 127

        for token in tokens:
            token_parts = sorted(self._split_token(token),
                                 key=lambda part: (
                                     self.sort_order.index(part[0]) if part[0] in self.sort_order else -1))
            main_parts = [part[0] for part in token_parts]

            for i, main_part in enumerate(main_parts):
                if main_part == TokenisationPrefixes.PAD.value:
                    continue
                elif main_part == TokenisationPrefixes.START.value:
                    continue
                elif main_part == TokenisationPrefixes.STOP.value:
                    continue
                elif main_part == TokenisationPrefixes.BAR.value:
                    cur_time += cur_bar_capacity_remaining
                    cur_time_bar = 0
                    cur_bar_capacity_remaining = cur_bar_capacity_total

                    for sequence in sequences:
                        sequence.add_absolute_message(Message(message_type=MessageType.INTERNAL, time=cur_time))
                elif main_part == TokenisationPrefixes.REST.value:
                    cur_time += int(token_parts[i][1])
                    cur_time_bar += int(token_parts[i][1])
                    cur_bar_capacity_remaining -= int(token_parts[i][1])
                elif main_part == TokenisationPrefixes.POSITION.value:
                    nxt_time_bar = int(token_parts[i][1])
                    nxt_time_shift = nxt_time_bar - cur_time_bar

                    if nxt_time_bar < cur_time_bar:
                        LOGGER.info("Skipping backward bar position")
                    else:
                        cur_time += nxt_time_shift
                        cur_time_bar += nxt_time_shift
                        cur_bar_capacity_remaining -= nxt_time_shift
                elif main_part == TokenisationPrefixes.TRACK.value:
                    prv_track = int(token_parts[i][1])
                elif main_part == TokenisationPrefixes.VALUE.value:
                    prv_value = int(token_parts[i][1])
                elif main_part == TokenisationPrefixes.VELOCITY.value:
                    prv_velocity = int(token_parts[i][1])
                elif main_part == TokenisationPrefixes.PITCH.value:
                    note_pitch = int(token_parts[i][1])

                    sequences[prv_track].add_absolute_message(
                        Message(message_type=MessageType.NOTE_ON, note=note_pitch, time=cur_time,
                                velocity=prv_velocity)
                    )
                    sequences[prv_track].add_absolute_message(
                        Message(message_type=MessageType.NOTE_OFF, note=note_pitch, time=cur_time + prv_value)
                    )
                elif main_part == TokenisationPrefixes.TIME_SIGNATURE.value:
                    if cur_time_bar > 0:
                        LOGGER.info(
                            f"Skipping time signature change mid-bar at time {cur_time} (bar time {cur_time_bar})")
                    else:
                        switched = False

                        new_time_signature_numerator = int(token_parts[i][1])
                        new_time_signature_denominator = int(token_parts[i][2])

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

                        if switched or not self.flag_running_values:
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
        info_pos_bar = []
        info_time = []
        info_time_bar = []
        info_pitch = []
        info_cof = []

        # Setup Values
        cur_pos = 0
        cur_pos_bar = 0
        cur_time = 0
        cur_time_bar = 0
        cur_time_signature_numerator = DEFAULT_TIME_SIGNATURE_NUMERATOR
        cur_time_signature_denominator = DEFAULT_TIME_SIGNATURE_DENOMINATOR
        cur_bar_capacity_total = int(self.ppqn * 4 * cur_time_signature_numerator / cur_time_signature_denominator)
        cur_bar_capacity_remaining = cur_bar_capacity_total
        prv_pitch = 69  # Concert pitch A4

        for token in tokens:
            token_parts = sorted(self._split_token(token),
                                 key=lambda part: (
                                     self.sort_order.index(part[0]) if part[0] in self.sort_order else -1))
            main_parts = [part[0] for part in token_parts]
            main_part = main_parts[0]

            info_pos.append(cur_pos)
            info_pos_bar.append(cur_pos_bar)
            info_time.append(cur_time)
            info_time_bar.append(cur_time_bar)

            cur_pos += 1
            cur_pos_bar += 1

            if main_part == TokenisationPrefixes.BAR.value:
                cur_time += cur_bar_capacity_remaining
                cur_pos_bar = 0
                cur_time_bar = 0
                cur_bar_capacity_remaining = cur_bar_capacity_total

                if not flag_impute_values:
                    info_pitch.append(math.nan)
                    info_cof.append(math.nan)
                else:
                    info_pitch.append(prv_pitch)
                    info_cof.append(CircleOfFifths.get_position(prv_pitch))
            elif main_part == TokenisationPrefixes.REST.value:
                cur_time += int(token_parts[0][1])
                cur_time_bar += int(token_parts[0][1])
                cur_bar_capacity_remaining -= int(token_parts[0][1])

                if not flag_impute_values:
                    info_pitch.append(math.nan)
                    info_cof.append(math.nan)
                else:
                    info_pitch.append(prv_pitch)
                    info_cof.append(CircleOfFifths.get_position(prv_pitch))
            elif main_part == TokenisationPrefixes.POSITION.value:
                nxt_time_bar = int(token_parts[0][1])
                nxt_time_shift = nxt_time_bar - cur_time_bar
                cur_time += nxt_time_shift
                cur_time_bar += nxt_time_shift
                cur_bar_capacity_remaining -= nxt_time_shift

                if not flag_impute_values:
                    info_pitch.append(math.nan)
                    info_cof.append(math.nan)
                else:
                    info_pitch.append(prv_pitch)
                    info_cof.append(CircleOfFifths.get_position(prv_pitch))
            elif TokenisationPrefixes.PITCH.value in main_parts:
                pitch_part = next(part for part in token_parts if part[0] == TokenisationPrefixes.PITCH.value)
                note_pitch = int(pitch_part[1])

                info_pitch.append(note_pitch)
                info_cof.append(CircleOfFifths.get_position(note_pitch))
            elif main_part == TokenisationPrefixes.TIME_SIGNATURE.value:
                if cur_time_bar > 0:
                    LOGGER.info(
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

        return {"info_position": info_pos,
                "info_position_bar": info_pos_bar,
                "info_time": info_time,
                "info_time_bar": info_time_bar,
                "info_pitch": info_pitch,
                "info_circle_of_fifths": info_cof}

    @staticmethod
    def _split_token(token: str):
        parts = token.split("-")
        sub_parts = [part.split("_") for part in parts]
        return sub_parts

    def _construct_dictionary(self):
        self.dictionary[TokenisationPrefixes.PAD.value] = self.dictionary_size
        self._dictionary_size += 1

        self.dictionary[TokenisationPrefixes.START.value] = self.dictionary_size
        self._dictionary_size += 1

        self.dictionary[TokenisationPrefixes.STOP.value] = self.dictionary_size
        self._dictionary_size += 1

        if self.flag_bar_token:
            self.dictionary[TokenisationPrefixes.BAR.value] = self.dictionary_size
            self._dictionary_size += 1

        if not self.flag_absolute_bar_position:
            for step_size in self.step_sizes:
                self.dictionary[f"{TokenisationPrefixes.REST.value}_{step_size:02}"] = self.dictionary_size
                self._dictionary_size += 1
        else:
            for position in range(1, int(self.bar_position_quarters_range * self.ppqn)):
                self.dictionary[f"{TokenisationPrefixes.POSITION.value}_{position:03}"] = self.dictionary_size
                self._dictionary_size += 1

        combinations = []

        if self.flag_fuse_track:
            combinations.append([track for track in range(self.num_tracks)])
        else:
            for track in range(self.num_tracks):
                self.dictionary[f"{TokenisationPrefixes.TRACK.value}_{track:02}"] = self.dictionary_size
                self._dictionary_size += 1
        combinations.append([pitch for pitch in range(self.pitch_range[0], self.pitch_range[1] + 1)])
        if self.flag_fuse_value:
            combinations.append([note_value for note_value in self.note_values])
        else:
            for note_value in self.note_values:
                self.dictionary[f"{TokenisationPrefixes.VALUE.value}_{note_value:02}"] = self.dictionary_size
                self._dictionary_size += 1
        if self.flag_fuse_velocity:
            combinations.append([velocity_bin for velocity_bin in self.velocity_bins])
        else:
            for velocity_bin in self.velocity_bins:
                self.dictionary[f"{TokenisationPrefixes.VELOCITY.value}_{velocity_bin:03}"] = self.dictionary_size
                self._dictionary_size += 1

        for combination in itertools.product(*combinations):
            parts = list(combination)
            token = ""

            if self.flag_fuse_track:
                token += f"{TokenisationPrefixes.TRACK.value}_{parts.pop(0):02}-"

            token += f"{TokenisationPrefixes.PITCH.value}_{parts.pop(0):03}-"

            if self.flag_fuse_value:
                token += f"{TokenisationPrefixes.VALUE.value}_{parts.pop(0):02}-"

            if self.flag_fuse_velocity:
                token += f"{TokenisationPrefixes.VELOCITY.value}_{parts.pop(0):03}"

            self.dictionary[token] = self.dictionary_size
            self._dictionary_size += 1

        if self.time_signature_range is not None:
            for time_signature in range(self.time_signature_range[0], self.time_signature_range[1] + 1):
                self.dictionary[
                    f"{TokenisationPrefixes.TIME_SIGNATURE.value}_{time_signature:02}_{DEFAULT_TIME_SIGNATURE_DENOMINATOR:02}"] = self.dictionary_size
                self._dictionary_size += 1

            self.inverse_dictionary = {v: k for k, v in self.dictionary.items()}
