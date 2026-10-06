"""Shared finite and compositional note-duration quantisation."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from scoda.errors import ValidationError

MAX_NOTE_DURATION_TICKS = 0x0FFFFFFF


@dataclass(frozen=True, slots=True)
class NoteDurationPolicy:
    """A duration palette, optionally repeated at a fixed tick interval.

    With extensions enabled the domain is ``n * duration_extension_ticks + v``
    for non-negative ``n`` and a configured base value ``v``. The extension
    interval equals the largest base value, making decomposition unique and
    exact multiples representable without a zero-duration note.
    """

    note_values: tuple[int, ...]
    duration_extension_ticks: int | None = None

    def __post_init__(self) -> None:
        raw: object = self.note_values
        if isinstance(raw, (str, bytes)):
            raise ValidationError("note_values must be a collection of positive integers")
        try:
            values = tuple(cast(Iterable[int], raw))
        except TypeError as exc:
            raise ValidationError("note_values must be a collection of positive integers") from exc
        if not values or any(
            isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= MAX_NOTE_DURATION_TICKS
            for value in values
        ):
            raise ValidationError("note_values must contain positive MIDI-representable durations")
        if len(set(values)) != len(values):
            raise ValidationError("note_values must not contain duplicates")
        object.__setattr__(self, "note_values", tuple(sorted(values)))
        unit = self.duration_extension_ticks
        if unit is not None and (isinstance(unit, bool) or not isinstance(unit, int) or unit != max(values)):
            raise ValidationError("duration_extension_ticks must equal the largest configured note value")

    @staticmethod
    def _validate_duration(duration: int) -> None:
        if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0:
            raise ValidationError("duration must be a positive integer")

    def floor(self, duration: int) -> int | None:
        """Return the largest representable duration not exceeding a gap."""
        self._validate_duration(duration)
        unit = self.duration_extension_ticks
        if unit is None:
            index = bisect_right(self.note_values, duration)
            return self.note_values[index - 1] if index else None
        if duration > MAX_NOTE_DURATION_TICKS:
            raise ValidationError("duration exceeds the supported MIDI note-duration range")
        count, remainder = divmod(duration - 1, unit)
        remainder += 1
        index = bisect_right(self.note_values, remainder)
        if index:
            return count * unit + self.note_values[index - 1]
        return count * unit if count else None

    def nearest(self, duration: int) -> int:
        """Return the nearest duration; an exact tie selects the shorter one."""
        self._validate_duration(duration)
        unit = self.duration_extension_ticks
        count, remainder = (0, duration) if unit is None else divmod(duration - 1, unit)
        if unit is not None:
            if duration > MAX_NOTE_DURATION_TICKS:
                raise ValidationError("duration exceeds the supported MIDI note-duration range")
            remainder += 1
        index = bisect_left(self.note_values, remainder)
        lower = self.floor(duration)
        if index < len(self.note_values):
            upper = count * (unit or 0) + self.note_values[index]
        else:
            upper = self.note_values[-1]
        if upper > MAX_NOTE_DURATION_TICKS:
            if lower is None:
                raise ValidationError("quantised duration exceeds the supported MIDI note-duration range")
            return lower
        if lower is None:
            return upper
        return lower if duration - lower <= upper - duration else upper

    def decompose(self, duration: int) -> tuple[int, int]:
        """Return the unique extension count and base value of a duration."""
        self._validate_duration(duration)
        if duration > MAX_NOTE_DURATION_TICKS:
            raise ValidationError("duration exceeds the supported MIDI note-duration range")
        unit = self.duration_extension_ticks
        count, base = (0, duration) if unit is None else divmod(duration - 1, unit)
        if unit is not None:
            base += 1
        if base not in self.note_values:
            raise ValidationError("duration is outside the configured duration domain")
        return count, base
