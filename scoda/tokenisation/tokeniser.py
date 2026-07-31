"""Canonical notelike tokenisation for immutable S-Coda sequences."""

from __future__ import annotations

import hashlib
import json
import math
import operator
from abc import ABC, abstractmethod
from bisect import bisect_left
from collections.abc import Iterable, Mapping
from collections.abc import Sequence as TypingSequence
from dataclasses import asdict, dataclass, replace
from heapq import merge
from types import MappingProxyType
from typing import Any, Literal, cast

from scoda.core import Note, Sequence, SequenceBuilder, TimeSignature, bar_spans
from scoda.errors import TokenisationError
from scoda.music_theory import _circle_of_fifths_position

_MAX_VOCABULARY_SIZE = 250_000
_MAX_CACHED_TOKEN_REFERENCES = 1_000_000
_MAX_NOTE_VALUE = 0x0FFFFFFF


@dataclass(frozen=True, slots=True)
class VocabularyManifest:
    """Deterministic identity of one codec configuration and ordered vocabulary."""

    codec_id: str
    normalised_config_json: str
    tokens: tuple[str, ...]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.codec_id, str) or not self.codec_id:
            raise TokenisationError("manifest codec_id must be a non-empty string")
        if not isinstance(self.normalised_config_json, str):
            raise TokenisationError("manifest configuration must be JSON text")
        try:
            config = json.loads(self.normalised_config_json)
        except (TypeError, ValueError) as exc:
            raise TokenisationError("manifest configuration is not valid JSON") from exc
        if not isinstance(config, dict):
            raise TokenisationError("manifest configuration must decode to an object")
        try:
            config_json = json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise TokenisationError("manifest configuration must contain finite JSON values") from exc
        object.__setattr__(self, "normalised_config_json", config_json)
        token_values: object = self.tokens
        if isinstance(token_values, (str, bytes)):
            raise TokenisationError("manifest tokens must be a sequence of token strings")
        try:
            tokens = tuple(cast(Iterable[str], token_values))
        except TypeError as exc:
            raise TokenisationError("manifest tokens must be a sequence of token strings") from exc
        if not all(isinstance(token, str) and token for token in tokens):
            raise TokenisationError("manifest tokens must be non-empty strings")
        if len(set(tokens)) != len(tokens):
            raise TokenisationError("manifest tokens must be unique")
        object.__setattr__(self, "tokens", tokens)
        payload = json.dumps(
            {"codec_id": self.codec_id, "config": config, "tokens": tokens},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        expected = hashlib.sha256(payload).hexdigest()
        if self.sha256 != expected:
            raise TokenisationError("manifest SHA-256 does not match its codec, configuration, and tokens")

    @property
    def size(self) -> int:
        """Return the number of tokens in the vocabulary."""

        return len(self.tokens)

    @property
    def normalised_config(self) -> dict[str, object]:
        """Return the canonical JSON configuration as a new dictionary."""

        return cast(dict[str, object], json.loads(self.normalised_config_json))


def _manifest(codec_id: str, config: Mapping[str, Any], tokens: Iterable[str]) -> VocabularyManifest:
    ordered = tuple(tokens)
    if len(set(ordered)) != len(ordered):
        raise TokenisationError("token vocabulary contains duplicate entries")
    try:
        config_json = json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise TokenisationError("manifest configuration must contain finite JSON values") from exc
    payload = json.dumps(
        {"codec_id": codec_id, "config": json.loads(config_json), "tokens": ordered},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return VocabularyManifest(codec_id, config_json, ordered, hashlib.sha256(payload).hexdigest())


@dataclass(frozen=True, slots=True)
class TokeniserState:
    """Immutable grammar state used for incremental constrained decoding."""

    started: bool = False
    ended: bool = False
    active_track: int | None = None
    bar_count: int = 0
    bar_position: int = 0
    bar_capacity: int = 96
    pending_note_ticks: int = 0
    meter_numerator: int = 4
    meter_denominator: int = 4
    meter_declared: bool = False
    position_track_floor: int = -1
    last_note_key: tuple[int, int, int] | None = None
    valid: bool = True
    phase: Literal["initial", "started", "bar", "bar_meter", "position", "track", "note", "ended"] = "initial"

    def __post_init__(self) -> None:
        for name in ("started", "ended", "meter_declared", "valid"):
            if not isinstance(getattr(self, name), bool):
                raise TokenisationError(f"tokeniser state {name} must be a boolean")
        if self.active_track is not None and (
            isinstance(self.active_track, bool) or not isinstance(self.active_track, int) or self.active_track < 0
        ):
            raise TokenisationError("tokeniser state active_track must be a non-negative integer or None")
        for name, minimum in (
            ("bar_count", 0),
            ("bar_position", 0),
            ("bar_capacity", 1),
            ("pending_note_ticks", 0),
            ("meter_numerator", 1),
            ("meter_denominator", 1),
            ("position_track_floor", -1),
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise TokenisationError(f"tokeniser state {name} must be an integer of at least {minimum}")
        if self.bar_position > self.bar_capacity:
            raise TokenisationError("tokeniser state bar_position exceeds bar_capacity")
        if self.meter_denominator & (self.meter_denominator - 1):
            raise TokenisationError("tokeniser state meter_denominator must be a power of two")
        if self.last_note_key is not None:
            if (
                not isinstance(self.last_note_key, tuple)
                or len(self.last_note_key) != 3
                or any(
                    isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in self.last_note_key
                )
            ):
                raise TokenisationError(
                    "tokeniser state last_note_key must contain three non-negative integers or None"
                )
        if self.phase not in {"initial", "started", "bar", "bar_meter", "position", "track", "note", "ended"}:
            raise TokenisationError(f"invalid tokeniser state phase: {self.phase!r}")
        if self.ended != (self.phase == "ended"):
            raise TokenisationError("tokeniser state ended flag and phase are inconsistent")
        if self.started == (self.phase == "initial"):
            raise TokenisationError("tokeniser state started flag and phase are inconsistent")


@dataclass(frozen=True, slots=True)
class TokenMetadata:
    """Per-token structural and musical metadata aligned with a token stream."""

    token_index: tuple[int, ...]
    token_index_in_bar: tuple[int, ...]
    tick: tuple[int, ...]
    tick_in_bar: tuple[int, ...]
    track_index: tuple[int | None, ...]
    pitch: tuple[int | float, ...]
    circle_of_fifths: tuple[int | float, ...]

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            raw: object = getattr(self, name)
            if isinstance(raw, (str, bytes)):
                raise TokenisationError(f"token metadata {name} must be an iterable")
            try:
                values = tuple(cast(Iterable[object], raw))
            except TypeError as exc:
                raise TokenisationError(f"token metadata {name} must be an iterable") from exc
            object.__setattr__(self, name, values)
        lengths = {len(getattr(self, name)) for name in self.__dataclass_fields__}
        if len(lengths) > 1:
            raise TokenisationError("token metadata fields must have equal lengths")
        for name in ("token_index", "token_index_in_bar", "tick", "tick_in_bar"):
            if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in getattr(self, name)):
                raise TokenisationError(f"token metadata {name} must contain non-negative integers")
        if any(
            value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0)
            for value in self.track_index
        ):
            raise TokenisationError("token metadata track_index must contain non-negative integers or None")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or (isinstance(value, int) and not 0 <= value <= 127)
            or (isinstance(value, float) and not (math.isnan(value) or 0 <= value <= 127))
            for value in self.pitch
        ):
            raise TokenisationError("token metadata pitch must contain MIDI pitches or NaN")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or (isinstance(value, int) and not -5 <= value <= 6)
            or (isinstance(value, float) and not (math.isnan(value) or -5 <= value <= 6))
            for value in self.circle_of_fifths
        ):
            raise TokenisationError("token metadata circle_of_fifths must contain positions or NaN")

    def __len__(self) -> int:
        """Return the number of tokens represented by this metadata."""

        return len(self.token_index)

    def _slice(self, start: int, stop: int) -> TokenMetadata:
        return TokenMetadata(
            self.token_index[start:stop],
            self.token_index_in_bar[start:stop],
            self.tick[start:stop],
            self.tick_in_bar[start:stop],
            self.track_index[start:stop],
            self.pitch[start:stop],
            self.circle_of_fifths[start:stop],
        )


class _IncrementalTokeniser(ABC):
    config: NotelikeConfig
    token_to_id: Mapping[str, int]
    vocabulary: tuple[str, ...]

    @property
    def num_tracks(self) -> int:
        """Return the number of synchronised tracks expected by the tokeniser."""

        return self.config.num_tracks

    @property
    def ticks_per_quarter(self) -> int:
        """Return the tokeniser's tick resolution."""

        return self.config.ticks_per_quarter

    def _initialise_incremental_cache(self) -> None:
        self._allowed_token_cache: dict[tuple[object, ...], frozenset[int]] = {}
        self._allowed_token_cache_limit = max(
            8,
            min(4096, _MAX_CACHED_TOKEN_REFERENCES // max(1, len(self.vocabulary))),
        )
        token_ids_by_main: dict[str, set[int]] = {}
        for token_id, token in enumerate(self.vocabulary):
            main = token.partition("_")[0]
            token_ids_by_main.setdefault(main, set()).add(token_id)
        self._token_ids_by_main = {main: frozenset(token_ids) for main, token_ids in token_ids_by_main.items()}

    @property
    def start_token_id(self) -> int:
        """Return the vocabulary ID of the stream-start token."""

        return self.token_to_id["sta"]

    @property
    def stop_token_id(self) -> int:
        """Return the vocabulary ID of the stream-stop token."""

        return self.token_to_id["sto"]

    def initial_state(self) -> TokeniserState:
        """Return the grammar state before any token has been consumed."""

        return TokeniserState(bar_capacity=self.ticks_per_quarter * 4)

    def _validated_token_values(self, tokens: object, *, name: str) -> list[str]:
        if isinstance(tokens, (str, bytes)):
            raise TokenisationError(f"{name} must be a sequence of token strings, not a string")
        if not isinstance(tokens, Iterable):
            raise TokenisationError(f"{name} must be an iterable of token strings")
        try:
            values = list(tokens)
        except TypeError as exc:
            raise TokenisationError(f"{name} must be an iterable of token strings") from exc
        if not all(isinstance(token, str) for token in values):
            raise TokenisationError(f"{name} must contain only token strings")
        unknown = next((token for token in values if token not in self.token_to_id), None)
        if unknown is not None:
            raise TokenisationError(f"unknown token: {unknown}")
        return values

    def _validated_token_ids(self, token_ids: object) -> list[int]:
        if isinstance(token_ids, (str, bytes)) or not isinstance(token_ids, Iterable):
            raise TokenisationError("token_ids must be an iterable of integers")
        values: list[int] = []
        for token_id in token_ids:
            if isinstance(token_id, bool):
                raise TokenisationError(f"token id must be an integer, got {token_id!r}")
            try:
                values.append(operator.index(token_id))
            except TypeError as exc:
                raise TokenisationError(f"token id must be an integer, got {token_id!r}") from exc
        return values

    def frame(self, tokens: TypingSequence[str]) -> list[str]:
        """Wrap an unframed token body in exactly one start/stop pair."""

        body = self._validated_token_values(tokens, name="token body")
        if any(token in {"sta", "sto"} for token in body):
            raise TokenisationError("token body must not contain start or stop tokens")
        return ["sta", *body, "sto"]

    def unframe(self, tokens: TypingSequence[str]) -> list[str]:
        """Remove one required start/stop pair from a complete token stream."""

        values = self._validated_token_values(tokens, name="token stream")
        if len(values) < 2 or values[0] != "sta" or values[-1] != "sto":
            raise TokenisationError("token stream must start with 'sta' and end with 'sto'")
        if any(token in {"sta", "sto"} for token in values[1:-1]):
            raise TokenisationError("token stream contains a nested start or stop token")
        return values[1:-1]

    @staticmethod
    def _parts(token: str) -> list[list[str]]:
        return [part.split("_") for part in token.split("-") if part]

    @staticmethod
    def _number(part: list[str], index: int) -> int | None:
        try:
            return int(part[index])
        except (IndexError, TypeError, ValueError):
            return None

    @abstractmethod
    def _transition(
        self,
        state: TokeniserState,
        token: str,
        *,
        materialise: bool,
    ) -> TokeniserState | None:
        """Validate one transition and optionally construct its resulting state."""

    def _advance_token(self, state: TokeniserState, token: str) -> TokeniserState | None:
        return self._transition(state, token, materialise=True)

    def _accepts_token(self, state: TokeniserState, token: str) -> bool:
        return self._transition(state, token, materialise=False) is not None

    def advance(self, state: TokeniserState, token_id: int) -> TokeniserState:
        """Consume one allowed token ID and return the next immutable state."""

        self._validate_state(state)
        if isinstance(token_id, bool):
            raise TokenisationError(f"token id must be an integer, got {token_id!r}")
        try:
            index = operator.index(token_id)
        except TypeError as exc:
            raise TokenisationError(f"token id must be an integer, got {token_id!r}") from exc
        token = self.vocabulary[index] if 0 <= index < len(self.vocabulary) else None
        next_state = None if token is None else self._advance_token(state, token)
        if next_state is None:
            raise TokenisationError(f"token id {token_id} is invalid after state {state}")
        return next_state

    def _validate_state(self, state: object) -> None:
        if not isinstance(state, TokeniserState):
            raise TokenisationError("state must be a TokeniserState value")
        if state.active_track is not None and state.active_track >= self.num_tracks:
            raise TokenisationError("tokeniser state active_track is outside the configured tracks")
        if state.position_track_floor >= self.num_tracks:
            raise TokenisationError("tokeniser state position_track_floor is outside the configured tracks")

    def inspect_prefix(self, token_ids: Iterable[int]) -> TokeniserState:
        """Validate an ID prefix and return the state after its final token."""

        state = self.initial_state()
        for token_id in self._validated_token_ids(token_ids):
            state = self.advance(state, token_id)
        return state

    def allowed_token_ids(self, state: TokeniserState) -> frozenset[int]:
        """Return every vocabulary ID accepted after ``state``."""

        if not isinstance(state, TokeniserState):
            raise TokenisationError("state must be a TokeniserState value")
        num_tracks = self.config.num_tracks
        if state.active_track is not None and state.active_track >= num_tracks:
            raise TokenisationError("tokeniser state active_track is outside the configured tracks")
        if state.position_track_floor >= num_tracks:
            raise TokenisationError("tokeniser state position_track_floor is outside the configured tracks")
        key = (
            state.started,
            state.ended,
            state.active_track,
            state.bar_count == 0,
            state.bar_position,
            state.bar_capacity,
            state.pending_note_ticks == 0,
            state.meter_numerator,
            state.meter_denominator,
            state.meter_declared,
            state.position_track_floor,
            state.last_note_key,
            state.valid,
            state.phase,
        )
        cached = self._allowed_token_cache.get(key)
        if cached is not None:
            return cached
        allowed = frozenset(
            token_id
            for token_id in self._candidate_token_ids(state)
            if 0 <= token_id < len(self.vocabulary)
            if (token := self.vocabulary[token_id]) is not None
            if self._accepts_token(state, token)
        )
        if len(self._allowed_token_cache) >= self._allowed_token_cache_limit:
            oldest = next(iter(self._allowed_token_cache), None)
            if oldest is not None:
                self._allowed_token_cache.pop(oldest, None)
        self._allowed_token_cache[key] = allowed
        return allowed

    def _candidate_token_ids(self, state: TokeniserState) -> Iterable[int]:
        return range(len(self.vocabulary))

    def state_key(self, state: TokeniserState) -> tuple[object, ...]:
        """Return the compact grammar key used for reusable constraint masks."""
        self._validate_state(state)
        return self._grammar_state_key(state)

    @staticmethod
    def _grammar_state_key(state: TokeniserState) -> tuple[object, ...]:
        return (
            state.started,
            state.ended,
            state.active_track,
            state.bar_count == 0,
            state.bar_position,
            state.bar_capacity,
            state.pending_note_ticks == 0,
            state.meter_numerator,
            state.meter_denominator,
            state.meter_declared,
            state.position_track_floor,
            state.last_note_key,
            state.valid,
            state.phase,
        )


@dataclass(frozen=True, slots=True)
class NotelikeConfig:
    """Immutable configuration for :class:`NotelikeTokeniser`."""

    ticks_per_quarter: int = 24
    num_tracks: int = 1
    pitch_range: tuple[int, int] = (21, 108)
    # Common straight, triplet, and dotted durations between a sixteenth-note
    # triplet and a whole note at the default resolution of 24 ticks per
    # quarter.  Corpus pipelines should still pin the exact subset appropriate
    # for their data.
    note_values: tuple[int, ...] = (4, 6, 8, 9, 12, 16, 18, 24, 32, 36, 48, 64, 72, 96)
    velocity_bins: int = 1
    include_time_signatures: bool = False
    max_bar_quarters: int = 4

    def __post_init__(self) -> None:
        try:
            pitch_range = tuple(self.pitch_range)
            note_values = tuple(self.note_values)
        except TypeError as exc:
            raise TokenisationError("pitch_range and note_values must be finite collections") from exc
        object.__setattr__(self, "pitch_range", pitch_range)
        object.__setattr__(self, "note_values", note_values)
        positive_integers = (self.ticks_per_quarter, self.num_tracks, self.velocity_bins, self.max_bar_quarters)
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in positive_integers):
            raise TokenisationError(
                "ticks_per_quarter, num_tracks, velocity_bins, and max_bar_quarters must be positive integers"
            )
        if self.max_bar_quarters < 4:
            raise TokenisationError("max_bar_quarters must accommodate the default 4/4 meter")
        if self.max_bar_quarters > 64:
            raise TokenisationError("max_bar_quarters must not exceed the largest representable meter")
        if self.ticks_per_quarter > 0x7FFF:
            raise TokenisationError("ticks_per_quarter must not exceed the standard MIDI PPQN limit of 32767")
        if self.velocity_bins > 127:
            raise TokenisationError("velocity_bins must not exceed the 127 positive MIDI velocities")
        if not isinstance(self.include_time_signatures, bool):
            raise TokenisationError("include_time_signatures must be a boolean")
        if not self.note_values or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in self.note_values
        ):
            raise TokenisationError("note_values must contain positive durations")
        if any(value > _MAX_NOTE_VALUE for value in self.note_values):
            raise TokenisationError(f"note_values must not exceed {_MAX_NOTE_VALUE} ticks")
        if len(set(self.note_values)) != len(self.note_values):
            raise TokenisationError("note_values must not contain duplicates")
        object.__setattr__(self, "note_values", tuple(sorted(self.note_values)))
        if (
            len(self.pitch_range) != 2
            or any(isinstance(value, bool) or not isinstance(value, int) for value in self.pitch_range)
            or not 0 <= self.pitch_range[0] <= self.pitch_range[1] <= 127
        ):
            raise TokenisationError("pitch_range must be inside MIDI pitch bounds")
        position_tokens = self.max_bar_quarters * self.ticks_per_quarter - 1
        note_tokens = (self.pitch_range[1] - self.pitch_range[0] + 1) * len(self.note_values) * self.velocity_bins
        meter_tokens = 96 if self.include_time_signatures else 0
        vocabulary_size_bound = 4 + position_tokens + self.num_tracks + note_tokens + meter_tokens
        if vocabulary_size_bound > _MAX_VOCABULARY_SIZE:
            raise TokenisationError(
                f"configuration may create at most {_MAX_VOCABULARY_SIZE} vocabulary entries; "
                f"requested upper bound is {vocabulary_size_bound}"
            )


class NotelikeTokeniser(_IncrementalTokeniser):
    """Canonical notelike grammar with explicit immutable configuration."""

    codec_id = "notelike"

    def __init__(self, config: NotelikeConfig | None = None) -> None:
        if config is not None and not isinstance(config, NotelikeConfig):
            raise TokenisationError("config must be a NotelikeConfig value")
        self.config = config if config is not None else NotelikeConfig()
        tokens = ["pad", "sta", "sto", "bar"]
        tokens.extend(
            f"pos_{position:03}" for position in range(1, self.config.max_bar_quarters * self.ticks_per_quarter)
        )
        tokens.extend(f"trk_{track:02}" for track in range(self.num_tracks))
        velocities = tuple(
            ((2 * index + 1) * 127 + self.config.velocity_bins) // (2 * self.config.velocity_bins)
            for index in range(self.config.velocity_bins)
        )
        self._velocity_values = velocities
        tokens.extend(
            f"pit_{pitch:03}-val_{value:02}-vel_{velocity:03}"
            for pitch in range(self.config.pitch_range[0], self.config.pitch_range[1] + 1)
            for value in self.config.note_values
            for velocity in velocities
        )
        if self.config.include_time_signatures:
            tokens.extend(
                f"tsg_{numerator:02}_{denominator:02}"
                for denominator in (1, 2, 4, 8, 16, 32)
                for numerator in range(1, 17)
                if (self.ticks_per_quarter * 4 * numerator) % denominator == 0
                and (self.ticks_per_quarter * 4 * numerator) // denominator
                <= self.config.max_bar_quarters * self.ticks_per_quarter
            )
        self.manifest = _manifest(self.codec_id, asdict(self.config), tokens)
        self.vocabulary = self.manifest.tokens
        token_to_id = {token: index for index, token in enumerate(self.vocabulary)}
        if len(token_to_id) != self.manifest.size:
            raise TokenisationError("token vocabulary is not a contiguous bijection")
        self.token_to_id = MappingProxyType(token_to_id)
        self._position_token_ids = MappingProxyType(
            {int(token.split("_")[1]): token_id for token, token_id in token_to_id.items() if token.startswith("pos_")}
        )
        self._bar_token_id = token_to_id["bar"]
        self._position_tokens = MappingProxyType(
            {position: f"pos_{position:03}" for position in self._position_token_ids}
        )

        def nearest_velocity(value: int) -> int:
            return min(self._velocity_values, key=lambda candidate: abs(candidate - value))

        self._velocity_lookup = tuple(nearest_velocity(value) for value in range(128))
        self._note_tokens = MappingProxyType(
            {
                (pitch, value, velocity): f"pit_{pitch:03}-val_{value:02}-vel_{velocity:03}"
                for pitch in range(self.config.pitch_range[0], self.config.pitch_range[1] + 1)
                for value in self.config.note_values
                for velocity in self._velocity_values
            }
        )
        self._initialise_incremental_cache()

    def __reduce__(self) -> tuple[type[NotelikeTokeniser], tuple[NotelikeConfig]]:
        """Reconstruct the immutable codec from its config when pickled.

        The derived lookup tables intentionally use read-only mapping proxies,
        which Python's default pickler cannot serialise. The complete codec is
        deterministic from :attr:`config`, so multiprocessing workers can
        safely and compactly rebuild it instead of serialising derived state.
        """
        return (NotelikeTokeniser, (self.config,))

    def _transition(
        self,
        state: TokeniserState,
        token: str,
        *,
        materialise: bool,
    ) -> TokeniserState | None:
        """Validate or advance the strict end-of-bar grammar."""

        if not isinstance(state, TokeniserState) or not state.valid or state.ended:
            return None
        parts = self._parts(token)
        if not parts:
            return None
        main = parts[0][0]
        prefixes = {part[0] for part in parts}
        if main == "pad":
            return None
        if main == "sta":
            if state.phase != "initial" or state.started or state.bar_count != 0:
                return None
            if not materialise:
                return state
            return replace(state, started=True, phase="bar")
        if not state.started:
            return None
        if main == "sto":
            if state.phase not in {"bar", "position"}:
                return None
            if state.pending_note_ticks:
                return None
            if not materialise:
                return state
            return replace(state, ended=True, phase="ended")
        if main == "bar":
            if state.phase not in {"bar", "bar_meter", "position", "note"}:
                return None
            if self.config.include_time_signatures and not state.meter_declared:
                return None
            if not materialise:
                return state
            remaining = state.bar_capacity - state.bar_position
            return replace(
                state,
                bar_count=state.bar_count + 1,
                bar_position=0,
                pending_note_ticks=max(0, state.pending_note_ticks - remaining),
                position_track_floor=-1,
                last_note_key=None,
                phase="bar",
            )
        if main == "tsg":
            if not self.config.include_time_signatures or state.phase != "bar":
                return None
            numerator, denominator = self._number(parts[0], 1), self._number(parts[0], 2)
            if numerator is None or denominator is None or denominator == 0:
                return None
            capacity_numerator = self.ticks_per_quarter * 4 * numerator
            if capacity_numerator % denominator != 0:
                return None
            capacity = capacity_numerator // denominator
            if capacity <= 0 or capacity > self.config.max_bar_quarters * self.ticks_per_quarter:
                return None
            meter = (numerator, denominator)
            if state.meter_declared and meter == (state.meter_numerator, state.meter_denominator):
                return None
            if not materialise:
                return state
            return replace(
                state,
                bar_capacity=capacity,
                meter_numerator=numerator,
                meter_denominator=denominator,
                meter_declared=True,
                phase="bar_meter",
            )
        if main == "pos":
            if state.phase not in {"bar", "bar_meter", "note"}:
                return None
            if self.config.include_time_signatures and not state.meter_declared:
                return None
            position = self._number(parts[0], 1)
            if position is None or not state.bar_position < position < state.bar_capacity:
                return None
            if not materialise:
                return state
            delta = position - state.bar_position
            return replace(
                state,
                bar_position=position,
                pending_note_ticks=max(0, state.pending_note_ticks - delta),
                position_track_floor=-1,
                last_note_key=None,
                phase="position",
            )
        if main == "rst":
            return None

        track_part = next((part for part in parts if part[0] == "trk"), None)
        if main == "trk":
            if state.bar_position >= state.bar_capacity or state.phase not in {"bar", "bar_meter", "position", "note"}:
                return None
            if self.config.include_time_signatures and not state.meter_declared:
                return None
            track = None if track_part is None else self._number(track_part, 1)
            if track is None or not 0 <= track < self.num_tracks:
                return None
            if track == state.active_track or track <= state.position_track_floor:
                return None
            if not materialise:
                return state
            return replace(
                state,
                active_track=track,
                position_track_floor=track,
                last_note_key=None,
                phase="track",
            )
        if "pit" in prefixes:
            if state.bar_position >= state.bar_capacity or state.phase not in {
                "bar",
                "bar_meter",
                "track",
                "position",
                "note",
            }:
                return None
            if self.config.include_time_signatures and not state.meter_declared:
                return None
            if state.active_track is None:
                return None
            pitch_part = next((part for part in parts if part[0] == "pit"), None)
            value_part = next((part for part in parts if part[0] == "val"), None)
            velocity_part = next((part for part in parts if part[0] == "vel"), None)
            if pitch_part is None or value_part is None or velocity_part is None:
                return None
            pitch = self._number(pitch_part, 1)
            value = self._number(value_part, 1)
            velocity = self._number(velocity_part, 1)
            if pitch is None or value is None or velocity is None:
                return None
            note_key = (pitch, value, velocity)
            if state.last_note_key is not None and note_key < state.last_note_key:
                return None
            active_track = state.active_track
            if active_track < state.position_track_floor:
                return None
            if not materialise:
                return state
            return replace(
                state,
                pending_note_ticks=max(state.pending_note_ticks, value),
                position_track_floor=active_track,
                last_note_key=note_key,
                phase="note",
            )
        return None

    def _candidate_token_ids(self, state: TokeniserState) -> frozenset[int]:
        mains: set[str] = set()
        if state.phase == "initial":
            mains.add("sta")
        elif not state.ended:
            if state.phase == "bar":
                mains.update(("sto", "bar", "tsg"))
            if state.phase in {"bar", "bar_meter", "note"}:
                mains.add("pos")
            if state.phase in {"bar", "bar_meter", "position", "note"}:
                mains.add("trk")
            if state.phase in {"track", "position", "note"}:
                mains.add("pit")
            if state.active_track is not None and state.phase in {"bar", "bar_meter"}:
                mains.add("pit")
            if state.phase in {"bar_meter", "position", "note"}:
                mains.add("bar")
            if state.phase == "position":
                mains.add("sto")
        return frozenset(token_id for main in mains for token_id in self._token_ids_by_main.get(main, ()))

    @property
    def vocabulary_size(self) -> int:
        """Return the number of tokens in the vocabulary."""

        return len(self.vocabulary)

    def encode(self, tokens: TypingSequence[str]) -> list[int]:
        """Encode token strings as vocabulary IDs."""

        return [self.token_to_id[token] for token in self._validated_token_values(tokens, name="tokens")]

    def decode(self, token_ids: TypingSequence[int]) -> list[str]:
        """Decode vocabulary IDs as token strings."""

        decoded = []
        for token_id in self._validated_token_ids(token_ids):
            if not 0 <= token_id < len(self.vocabulary):
                raise TokenisationError(f"unknown token id: {token_id}")
            decoded.append(self.vocabulary[token_id])
        return decoded

    def tokenise(self, sequences: TypingSequence[Sequence]) -> list[str]:
        """Return a complete framed canonical stream for synchronised sequences."""

        return self.frame(self.tokenise_body(sequences))

    def tokenise_body(self, sequences: object) -> list[str]:
        """Return the canonical, deliberately lossy stream body without framing."""

        if isinstance(sequences, (str, bytes)):
            raise TokenisationError("tokenise_body expects a sequence of immutable Sequence values")
        if not isinstance(sequences, Iterable):
            raise TokenisationError("tokenise_body expects a sequence of immutable Sequence values")
        sequence_values = tuple(sequences)
        if len(sequence_values) != self.num_tracks:
            raise TokenisationError("number of sequences does not match num_tracks")
        if not all(isinstance(sequence, Sequence) for sequence in sequence_values):
            raise TokenisationError("tokenise_body expects immutable Sequence values")
        typed_sequences = cast(tuple[Sequence, ...], sequence_values)
        if any(sequence.ticks_per_quarter != self.ticks_per_quarter for sequence in typed_sequences):
            raise TokenisationError("sequence PPQN does not match tokeniser configuration")
        track_notes: list[tuple[tuple[int, int, int, int, int], ...]] = []
        effective_duration = max(sequence.duration_ticks for sequence in typed_sequences)
        for track, sequence in enumerate(typed_sequences):
            quantised_notes = []
            for note in sequence.notes:
                if not self.config.pitch_range[0] <= note.pitch <= self.config.pitch_range[1]:
                    raise TokenisationError(f"note pitch {note.pitch} is outside the configured pitch range")
                raw_duration = note.end - note.start
                insertion_index = bisect_left(self.config.note_values, raw_duration)
                if insertion_index == 0:
                    value = self.config.note_values[0]
                elif insertion_index == len(self.config.note_values):
                    value = self.config.note_values[-1]
                else:
                    lower = self.config.note_values[insertion_index - 1]
                    upper = self.config.note_values[insertion_index]
                    value = lower if raw_duration - lower <= upper - raw_duration else upper
                velocity = self._velocity_lookup[note.velocity]
                quantised_notes.append((note.start, track, note.pitch, value, velocity))
                effective_duration = max(effective_duration, note.start + value)
            track_notes.append(tuple(sorted(quantised_notes)))
        notes = tuple(merge(*track_notes, key=lambda item: item))
        tokens: list[str] = []
        duration = effective_duration
        if self.config.include_time_signatures:
            spans: tuple[tuple[int, int, TimeSignature | None], ...] = tuple(
                (span.start, span.end, span.time_signature) for span in bar_spans(typed_sequences[0].pad(duration))
            )
        else:
            # Without encoded meter changes, the grammar has an implicit 4/4
            # meter. ``max_bar_quarters`` only bounds the position vocabulary
            # for longer explicitly encoded meters.
            bar_length = self.ticks_per_quarter * 4
            spans = tuple((start, min(duration, start + bar_length), None) for start in range(0, duration, bar_length))
        note_index = 0
        previous_meter: tuple[int, int] | None = None
        active_track = None
        for bar_start, bar_end, signature in spans:
            current_position = 0
            if signature is None:
                bar_capacity = self.ticks_per_quarter * 4
            else:
                capacity_numerator = self.ticks_per_quarter * 4 * signature.numerator
                if capacity_numerator % signature.denominator:
                    raise TokenisationError("bar length is not integral at the configured PPQN")
                bar_capacity = capacity_numerator // signature.denominator
            if signature is not None:
                meter = (signature.numerator, signature.denominator)
                if meter != previous_meter:
                    meter_token = f"tsg_{meter[0]:02}_{meter[1]:02}"
                    if meter_token not in self.token_to_id:
                        raise TokenisationError(
                            f"time signature {meter[0]}/{meter[1]} exceeds the configured meter vocabulary"
                        )
                    tokens.append(meter_token)
                    previous_meter = meter
            while note_index < len(notes) and notes[note_index][0] < bar_end:
                start, track, pitch, value, velocity = notes[note_index]
                if start < bar_start:
                    raise TokenisationError("a note falls outside the canonical bar partition")
                position = start - bar_start
                if position != current_position:
                    position_token = self._position_tokens.get(position)
                    if position_token is None:
                        raise TokenisationError(f"note position {position} is outside the configured bar")
                    tokens.append(position_token)
                    current_position = position
                if active_track != track:
                    tokens.append(f"trk_{track:02}")
                    active_track = track
                tokens.append(self._note_tokens[(pitch, value, velocity)])
                note_index += 1
            end_position = bar_end - bar_start
            if end_position == bar_capacity:
                tokens.append("bar")
            elif end_position != current_position:
                position_token = self._position_tokens.get(end_position)
                if position_token is None:
                    raise TokenisationError(f"bar endpoint {end_position} is outside the configured bar")
                tokens.append(position_token)
        return tokens

    def detokenise(self, tokens: TypingSequence[str]) -> tuple[Sequence, ...]:
        """Validate and decode a complete canonical stream into normalised tracks."""

        values = self._validated_token_values(tokens, name="token stream")
        self.unframe(values)
        builders = [SequenceBuilder(self.ticks_per_quarter) for _ in range(self.num_tracks)]
        state = self.initial_state()
        bar_start = 0
        for token in values:
            parts = self._parts(token)
            previous_capacity = state.bar_capacity
            next_state = self._advance_token(state, token)
            if next_state is None:
                raise TokenisationError(f"invalid token {token!r}")
            state = next_state
            prefixes = {part[0]: part for part in parts}
            if "tsg" in prefixes:
                builders[0].add_event(TimeSignature(bar_start, int(prefixes["tsg"][1]), int(prefixes["tsg"][2])))
            if "pit" in prefixes:
                pitch = int(prefixes["pit"][1])
                value = int(prefixes["val"][1])
                velocity = int(prefixes["vel"][1])
                if state.active_track is None:
                    raise TokenisationError("note token has no active track")
                start = bar_start + state.bar_position
                builders[state.active_track].add_note(
                    Note(start, start + value, pitch, velocity, state.active_track % 16)
                )
            if token == "bar":
                bar_start += previous_capacity
        duration = bar_start + state.bar_position
        for builder in builders:
            builder.set_duration(max(duration, builder.duration_ticks))
        result = tuple(builder.build() for builder in builders)
        if not state.ended:
            raise TokenisationError("token stream is incomplete")
        if self.tokenise(result) != values:
            raise TokenisationError("token stream is valid but not in canonical form")
        return result

    def body_metadata(
        self,
        tokens: TypingSequence[str],
        *,
        impute_pitch: bool = False,
    ) -> TokenMetadata:
        """Return metadata aligned one-to-one with an unframed token body."""

        body = self._validated_token_values(tokens, name="token body")
        return self.metadata(self.frame(body), impute_pitch=impute_pitch)._slice(1, -1)

    def metadata(
        self,
        tokens: TypingSequence[str],
        *,
        impute_pitch: bool = False,
    ) -> TokenMetadata:
        """Return metadata aligned one-to-one with a complete token stream."""

        if not isinstance(impute_pitch, bool):
            raise TokenisationError("impute_pitch must be a boolean")
        values = self._validated_token_values(tokens, name="token stream")
        self.unframe(values)
        state = self.initial_state()
        token_indexes: list[int] = []
        token_indexes_in_bar: list[int] = []
        ticks: list[int] = []
        ticks_in_bar: list[int] = []
        track_indexes: list[int | None] = []
        pitches: list[int | float] = []
        circle_of_fifths: list[int | float] = []
        absolute_bar_start = 0
        token_index_in_bar = 0
        previous_pitch = 69
        for token_index, token in enumerate(values):
            previous_state = state
            next_state = self._advance_token(state, token)
            if next_state is None:
                raise TokenisationError(f"invalid token {token!r}")
            state = next_state
            parts = self._parts(token)
            main = parts[0][0]
            pitch_part = next((part for part in parts if part[0] == "pit"), None)
            token_indexes.append(token_index)
            token_indexes_in_bar.append(token_index_in_bar)
            token_index_in_bar += 1
            if token == "bar":
                ticks.append(absolute_bar_start + previous_state.bar_capacity)
                ticks_in_bar.append(previous_state.bar_capacity)
            else:
                ticks.append(absolute_bar_start + state.bar_position)
                ticks_in_bar.append(state.bar_position)
            track_indexes.append(
                state.active_track
                if state.active_track is not None and (main == "trk" or pitch_part is not None)
                else None
            )
            if pitch_part is not None:
                previous_pitch = int(pitch_part[1])
                pitch_value: int | float = previous_pitch
            else:
                pitch_value = previous_pitch if impute_pitch else math.nan
            pitches.append(pitch_value)
            circle_of_fifths.append(
                _circle_of_fifths_position(int(pitch_value)) if math.isfinite(pitch_value) else math.nan
            )
            if token == "bar":
                absolute_bar_start += previous_state.bar_capacity
                token_index_in_bar = 0
        return TokenMetadata(
            tuple(token_indexes),
            tuple(token_indexes_in_bar),
            tuple(ticks),
            tuple(ticks_in_bar),
            tuple(track_indexes),
            tuple(pitches),
            tuple(circle_of_fifths),
        )


def create_tokeniser(
    codec_id: str,
    config: Mapping[str, object] | None = None,
) -> NotelikeTokeniser:
    """Construct a tokeniser from a persisted codec identifier and configuration."""

    if not isinstance(codec_id, str) or not codec_id:
        raise TokenisationError("codec_id must be a non-empty string")
    if codec_id != "notelike":
        raise TokenisationError(f"unknown tokeniser codec: {codec_id}")
    if config is not None and not isinstance(config, Mapping):
        raise TokenisationError("config must be a mapping or None")
    try:
        resolved = NotelikeConfig(**cast(Any, dict(config or {})))
    except TypeError as exc:
        raise TokenisationError(f"invalid tokeniser configuration: {exc}") from exc
    return NotelikeTokeniser(resolved)
