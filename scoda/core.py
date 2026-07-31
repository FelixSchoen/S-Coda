"""Immutable musical values and transformations used by S-Coda."""

from __future__ import annotations

from bisect import bisect_left
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Literal, TypeAlias, cast

from scoda.errors import SequenceError, ValidationError
from scoda.music_theory import Key


def _integer(name: str, value: int, minimum: int | None = None, maximum: int | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{name} must be an integer, got {value!r}")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{name} must be at least {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{name} must be at most {maximum}, got {value}")


def _positive_integer_values(name: str, values: object, *, allow_empty: bool = False) -> tuple[int, ...]:
    if isinstance(values, (str, bytes)):
        raise ValidationError(f"{name} must be an iterable of positive integers")
    try:
        result: tuple[object, ...] = tuple(cast(Iterable[object], values))
    except TypeError as exc:
        raise ValidationError(f"{name} must be an iterable of positive integers") from exc
    if (not result and not allow_empty) or any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in result
    ):
        raise ValidationError(f"{name} must contain positive integers")
    return cast(tuple[int, ...], result)


@dataclass(frozen=True, slots=True)
class Note:
    """A half-open MIDI note interval ``[start, end)`` in sequence ticks."""

    start: int
    end: int
    pitch: int
    velocity: int
    channel: int = 0
    release_velocity: int = 0

    def __post_init__(self) -> None:
        _integer("start", self.start, 0)
        _integer("end", self.end, 1)
        if self.end <= self.start:
            raise ValidationError("note end must be greater than note start")
        _integer("pitch", self.pitch, 0, 127)
        _integer("velocity", self.velocity, 1, 127)
        _integer("channel", self.channel, 0, 15)
        _integer("release_velocity", self.release_velocity, 0, 127)


@dataclass(frozen=True, slots=True)
class TimeSignature:
    """A MIDI time-signature event at an absolute sequence tick."""

    time: int
    numerator: int
    denominator: int
    clocks_per_click: int = 24
    notated_32nd_notes_per_beat: int = 8

    def __post_init__(self) -> None:
        _integer("time", self.time, 0)
        _integer("numerator", self.numerator, 1, 255)
        _integer("denominator", self.denominator, 1, 1 << 255)
        if self.denominator & (self.denominator - 1):
            raise ValidationError("time-signature denominator must be a power of two")
        _integer("clocks_per_click", self.clocks_per_click, 0, 255)
        _integer("notated_32nd_notes_per_beat", self.notated_32nd_notes_per_beat, 0, 255)


@dataclass(frozen=True, slots=True, init=False)
class KeySignature:
    """A MIDI key-signature event at an absolute sequence tick."""

    time: int
    key: Key

    def __init__(self, time: int, key: Key | str) -> None:
        object.__setattr__(self, "time", time)
        object.__setattr__(self, "key", key)
        self.__post_init__()

    def __post_init__(self) -> None:
        _integer("time", self.time, 0)
        raw_key: object = self.key
        if not isinstance(raw_key, Key):
            try:
                object.__setattr__(self, "key", Key(cast(str, raw_key)))
            except (TypeError, ValueError) as exc:
                raise ValidationError(f"invalid MIDI key signature: {raw_key!r}") from exc


@dataclass(frozen=True, slots=True)
class Tempo:
    """A MIDI tempo event expressed as microseconds per quarter note."""

    time: int
    microseconds_per_quarter: int

    def __post_init__(self) -> None:
        _integer("time", self.time, 0)
        _integer("microseconds_per_quarter", self.microseconds_per_quarter, 1, 0xFFFFFF)


@dataclass(frozen=True, slots=True)
class ControlChange:
    """A channel-specific MIDI controller update at an absolute tick."""

    time: int
    control: int
    value: int
    channel: int = 0

    def __post_init__(self) -> None:
        _integer("time", self.time, 0)
        _integer("control", self.control, 0, 127)
        _integer("value", self.value, 0, 127)
        _integer("channel", self.channel, 0, 15)


@dataclass(frozen=True, slots=True)
class ProgramChange:
    """A channel-specific MIDI program update at an absolute tick."""

    time: int
    program: int
    channel: int = 0

    def __post_init__(self) -> None:
        _integer("time", self.time, 0)
        _integer("program", self.program, 0, 127)
        _integer("channel", self.channel, 0, 15)


Event: TypeAlias = TimeSignature | KeySignature | Tempo | ControlChange | ProgramChange

_EVENT_ORDER = {
    TimeSignature: 0,
    KeySignature: 1,
    Tempo: 2,
    ProgramChange: 3,
    ControlChange: 3,
}


def _event_key(event: Event) -> tuple[int, int]:
    # Same-tick channel-state events remain in caller/source order. Their
    # relative order can be musically significant: bank-select controls must
    # precede program changes, and RPN/NRPN selection must precede data entry.
    return event.time, _EVENT_ORDER[type(event)]


@dataclass(frozen=True, slots=True)
class BarSpan:
    """An absolute bar interval with the musical context active at its start."""

    start: int
    end: int
    time_signature: TimeSignature
    key_signature: KeySignature | None = None

    def __post_init__(self) -> None:
        _integer("start", self.start, 0)
        _integer("end", self.end, self.start + 1)
        if not isinstance(self.time_signature, TimeSignature) or self.time_signature.time != self.start:
            raise ValidationError("bar time signature must be a TimeSignature at the bar start")
        if self.key_signature is not None and (
            not isinstance(self.key_signature, KeySignature) or self.key_signature.time != self.start
        ):
            raise ValidationError("bar key signature must occur at the bar start")

    @property
    def duration_ticks(self) -> int:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class Sequence:
    """Canonical immutable collection of notes, timed events, and duration."""

    notes: tuple[Note, ...] = ()
    events: tuple[Event, ...] = ()
    duration_ticks: int = 0
    ticks_per_quarter: int = 24

    def __post_init__(self) -> None:
        _integer("duration_ticks", self.duration_ticks, 0)
        _integer("ticks_per_quarter", self.ticks_per_quarter, 1)
        raw_notes: object = self.notes
        raw_events: object = self.events
        if isinstance(raw_notes, (str, bytes)) or isinstance(raw_events, (str, bytes)):
            raise ValidationError("notes and events must be iterable collections")
        try:
            notes = tuple(cast(Iterable[Note], raw_notes))
            events = tuple(cast(Iterable[Event], raw_events))
        except TypeError as exc:
            raise ValidationError("notes and events must be iterable collections") from exc
        if not all(isinstance(note, Note) for note in notes):
            raise ValidationError("notes must contain Note values")
        if not all(type(event) in _EVENT_ORDER for event in events):
            raise ValidationError("events contains an unsupported event value")
        notes = tuple(
            sorted(
                notes,
                key=lambda note: (
                    note.start,
                    note.end,
                    note.channel,
                    note.pitch,
                    note.velocity,
                    note.release_velocity,
                ),
            )
        )
        events = tuple(sorted(events, key=_event_key))
        latest = max(
            [0, *(note.end for note in notes), *(event.time for event in events)],
        )
        if latest > self.duration_ticks:
            raise ValidationError(f"duration_ticks={self.duration_ticks} ends before contained data at tick {latest}")
        object.__setattr__(self, "notes", notes)
        object.__setattr__(self, "events", events)

    @property
    def channel(self) -> int | None:
        channels = {note.channel for note in self.notes}
        channels.update(event.channel for event in self.events if isinstance(event, (ControlChange, ProgramChange)))
        return next(iter(channels)) if len(channels) == 1 else None

    def is_empty(self) -> bool:
        """Return whether the sequence contains no sounding notes."""

        return not self.notes

    def duration_relation(self, other: Sequence) -> float:
        """Return this duration divided by ``other`` in musical time."""

        if not isinstance(other, Sequence):
            raise ValidationError("other must be a Sequence")
        if other.duration_ticks == 0:
            return 1.0 if self.duration_ticks == 0 else float("inf")
        return (self.duration_ticks * other.ticks_per_quarter) / (other.duration_ticks * self.ticks_per_quarter)

    def similarity(
        self,
        other: Sequence,
        *,
        compare_velocity: bool = True,
        compare_channel: bool = True,
        compare_program: bool = True,
    ) -> float:
        """Return multiset overlap of note intervals and selected attributes."""

        if not isinstance(other, Sequence):
            raise ValidationError("other must be a Sequence")
        for name, value in (
            ("compare_velocity", compare_velocity),
            ("compare_channel", compare_channel),
            ("compare_program", compare_program),
        ):
            if not isinstance(value, bool):
                raise ValidationError(f"{name} must be a boolean")
        if self.ticks_per_quarter != other.ticks_per_quarter:
            raise SequenceError("cannot compare sequence similarity across different PPQN")

        def note_key(note: Note) -> tuple[int, ...]:
            values = [note.start, note.end, note.pitch]
            if compare_velocity:
                values.extend((note.velocity, note.release_velocity))
            if compare_channel:
                values.append(note.channel)
            return tuple(values)

        left = Counter(note_key(note) for note in self.notes)
        right = Counter(note_key(note) for note in other.notes)
        overlap = sum((left & right).values())
        note_total = max(sum(left.values()), sum(right.values()))
        score = 1.0 if note_total == 0 else overlap / note_total
        if compare_program:
            left_programs = Counter(
                (event.time, event.program, event.channel if compare_channel else None)
                for event in self.events
                if isinstance(event, ProgramChange)
            )
            right_programs = Counter(
                (event.time, event.program, event.channel if compare_channel else None)
                for event in other.events
                if isinstance(event, ProgramChange)
            )
            program_total = max(sum(left_programs.values()), sum(right_programs.values()))
            if program_total:
                program_score = sum((left_programs & right_programs).values()) / program_total
                score = program_score if note_total == 0 else (score + program_score) / 2
        return score

    def pad(self, duration_ticks: int) -> Sequence:
        """Extend the represented duration to at least ``duration_ticks``."""

        _integer("duration_ticks", duration_ticks, 0)
        return self if duration_ticks <= self.duration_ticks else replace(self, duration_ticks=duration_ticks)

    def cutoff(self, maximum_length: int, reduced_length: int | None = None) -> Sequence:
        """Shorten sequences above ``maximum_length`` to the selected target."""

        target = maximum_length if reduced_length is None else reduced_length
        _integer("maximum_length", maximum_length, 0)
        _integer("reduced_length", target, 0, maximum_length)
        if self.duration_ticks <= maximum_length:
            return self
        return self.slice(0, target)

    def with_channel(self, channel: int) -> Sequence:
        """Return a copy with every channel-specific value on ``channel``."""

        _integer("channel", channel, 0, 15)
        notes = tuple(replace(note, channel=channel) for note in self.notes)
        events = tuple(
            replace(event, channel=channel) if isinstance(event, (ControlChange, ProgramChange)) else event
            for event in self.events
        )
        return replace(self, notes=notes, events=events)

    def with_velocity(self, velocity: int | Callable[[int], int]) -> Sequence:
        """Return a copy with note velocities replaced or transformed."""

        if not callable(velocity):
            _integer("velocity", velocity, 1, 127)

        def value(current: int) -> int:
            result = velocity(current) if callable(velocity) else velocity
            _integer("velocity", result, 1, 127)
            return result

        return replace(self, notes=tuple(replace(note, velocity=value(note.velocity)) for note in self.notes))

    def filter_events(self, predicate: Callable[[Event], bool]) -> Sequence:
        """Return a copy containing only events accepted by ``predicate``."""

        if not callable(predicate):
            raise ValidationError("predicate must be callable")
        return replace(self, events=tuple(event for event in self.events if predicate(event)))

    def transpose(
        self,
        semitones: int,
        *,
        out_of_range: Literal["error", "drop", "octave_wrap"] = "error",
        pitch_range: tuple[int, int] = (0, 127),
    ) -> Sequence:
        """Transpose notes and key signatures by an integer number of semitones."""

        _integer("semitones", semitones)
        if out_of_range not in {"error", "drop", "octave_wrap"}:
            raise ValidationError(f"unknown out_of_range policy: {out_of_range!r}")
        if isinstance(pitch_range, (str, bytes)):
            raise ValidationError("pitch_range must contain exactly two integer bounds")
        try:
            bounds = tuple(pitch_range)
        except TypeError as exc:
            raise ValidationError("pitch_range must contain exactly two integer bounds") from exc
        if len(bounds) != 2:
            raise ValidationError("pitch_range must contain exactly two integer bounds")
        lower, upper = bounds
        _integer("pitch_range lower bound", lower, 0, 127)
        _integer("pitch_range upper bound", upper, lower, 127)
        transposed: list[Note] = []
        for note in self.notes:
            pitch = note.pitch + semitones
            if not lower <= pitch <= upper:
                if out_of_range == "drop":
                    continue
                if out_of_range == "octave_wrap":
                    if pitch < lower:
                        pitch += ((lower - pitch + 11) // 12) * 12
                    elif pitch > upper:
                        pitch -= ((pitch - upper + 11) // 12) * 12
                    if not lower <= pitch <= upper:
                        raise SequenceError("pitch range is too narrow for octave wrapping")
                elif out_of_range == "error":
                    raise SequenceError(f"transposition moves pitch {note.pitch} outside {pitch_range}")
            transposed.append(replace(note, pitch=pitch))
        events: list[Event] = []
        for event in self.events:
            if isinstance(event, KeySignature):
                events.append(replace(event, key=event.key.transpose(semitones)))
            else:
                events.append(event)
        return replace(self, notes=tuple(transposed), events=tuple(events))

    def quantise(self, step_sizes: Iterable[int]) -> Sequence:
        """Move note boundaries and event times to the nearest allowed grid point."""

        steps = tuple(sorted(set(_positive_integer_values("step_sizes", step_sizes))))

        def nearest(value: int) -> int:
            best = 0
            best_distance = value
            for step in steps:
                quotient, remainder = divmod(value, step)
                candidate = quotient * step if remainder * 2 <= step else (quotient + 1) * step
                distance = abs(candidate - value)
                if distance < best_distance or (distance == best_distance and candidate < best):
                    best = candidate
                    best_distance = distance
            return best

        notes = []
        for note in self.notes:
            start = nearest(note.start)
            end = nearest(note.end)
            if end <= start:
                end = start + min(steps)
            notes.append(replace(note, start=start, end=end))
        events = tuple(replace(event, time=nearest(event.time)) for event in self.events)
        duration = max(nearest(self.duration_ticks), *(note.end for note in notes), *(event.time for event in events))
        return replace(self, notes=tuple(notes), events=events, duration_ticks=duration)

    def quantise_note_lengths(self, note_values: Iterable[int]) -> Sequence:
        """Replace note durations with the nearest allowed note value."""

        values = tuple(sorted(set(_positive_integer_values("note_values", note_values))))

        def nearest(duration: int) -> int:
            index = bisect_left(values, duration)
            if index == 0:
                return values[0]
            if index == len(values):
                return values[-1]
            lower, upper = values[index - 1], values[index]
            return lower if duration - lower <= upper - duration else upper

        notes = tuple(
            replace(
                note,
                end=note.start + nearest(note.end - note.start),
            )
            for note in self.notes
        )
        duration = max(self.duration_ticks, *(note.end for note in notes))
        return replace(self, notes=notes, duration_ticks=duration)

    def quantise_and_normalise(self, step_sizes: Iterable[int], note_values: Iterable[int]) -> Sequence:
        """Quantise positions and durations while retaining canonical invariants."""

        return self.quantise(step_sizes).quantise_note_lengths(note_values)

    def resample(self, ticks_per_quarter: int) -> Sequence:
        """Return this sequence expressed at a different tick resolution."""

        _integer("ticks_per_quarter", ticks_per_quarter, 1)
        if ticks_per_quarter == self.ticks_per_quarter:
            return self
        ratio = Fraction(ticks_per_quarter, self.ticks_per_quarter)

        def scale(value: int) -> int:
            return round(value * ratio)

        notes = []
        for note in self.notes:
            start, end = scale(note.start), scale(note.end)
            if end <= start:
                end = start + 1
            notes.append(replace(note, start=start, end=end))
        events = tuple(replace(event, time=scale(event.time)) for event in self.events)
        duration = max(scale(self.duration_ticks), *(note.end for note in notes), *(event.time for event in events))
        return Sequence(tuple(notes), events, duration, ticks_per_quarter)

    def slice(self, start: int, end: int) -> Sequence:
        """Return the half-open tick window ``[start, end)`` with local timing."""

        _integer("start", start, 0)
        _integer("end", end, start)
        if end > self.duration_ticks:
            raise SequenceError("slice ends after sequence duration")
        if start == end:
            return Sequence((), (), 0, self.ticks_per_quarter)
        notes = tuple(
            Note(
                max(note.start, start) - start,
                min(note.end, end) - start,
                note.pitch,
                note.velocity,
                note.channel,
                note.release_velocity,
            )
            for note in self.notes
            if note.start < end and note.end > start
        )
        events = tuple(
            replace(event, time=event.time - start)
            for event in self.events
            if start <= event.time < end or (end == self.duration_ticks and event.time == end)
        )
        return Sequence(notes, events, end - start, self.ticks_per_quarter)

    def split(self, capacities: Iterable[int]) -> tuple[Sequence, ...]:
        """Split the sequence consecutively using the supplied tick capacities."""

        capacity_values = _positive_integer_values("capacities", capacities, allow_empty=True)
        boundaries = [0]
        for capacity in capacity_values:
            boundaries.append(min(self.duration_ticks, boundaries[-1] + capacity))
            if boundaries[-1] == self.duration_ticks:
                break
        if boundaries[-1] < self.duration_ticks:
            boundaries.append(self.duration_ticks)
        return tuple(self.slice(start, end) for start, end in zip(boundaries, boundaries[1:], strict=False))

    @classmethod
    def merge(cls, sequences: Iterable[Sequence]) -> Sequence:
        """Overlay sequences that share one tick resolution."""

        raw_sequences: object = sequences
        if isinstance(raw_sequences, (str, bytes)):
            raise ValidationError("sequences must be an iterable of Sequence values")
        try:
            values = tuple(cast(Iterable[Sequence], raw_sequences))
        except TypeError as exc:
            raise ValidationError("sequences must be an iterable of Sequence values") from exc
        if not values:
            return cls()
        if not all(isinstance(sequence, Sequence) for sequence in values):
            raise ValidationError("sequences must contain Sequence values")
        ppqn = values[0].ticks_per_quarter
        if any(sequence.ticks_per_quarter != ppqn for sequence in values):
            raise SequenceError("cannot merge sequences with different PPQN")
        return cls(
            tuple(note for sequence in values for note in sequence.notes),
            tuple(event for sequence in values for event in sequence.events),
            max(sequence.duration_ticks for sequence in values),
            ppqn,
        )

    @classmethod
    def concatenate(cls, sequences: Iterable[Sequence]) -> Sequence:
        """Join sequences end to end without changing their tick resolution."""

        raw_sequences: object = sequences
        if isinstance(raw_sequences, (str, bytes)):
            raise ValidationError("sequences must be an iterable of Sequence values")
        try:
            values = tuple(cast(Iterable[Sequence], raw_sequences))
        except TypeError as exc:
            raise ValidationError("sequences must be an iterable of Sequence values") from exc
        if not values:
            return cls()
        if not all(isinstance(sequence, Sequence) for sequence in values):
            raise ValidationError("sequences must contain Sequence values")
        ppqn = values[0].ticks_per_quarter
        if any(sequence.ticks_per_quarter != ppqn for sequence in values):
            raise SequenceError("cannot concatenate sequences with different PPQN")
        notes: list[Note] = []
        events: list[Event] = []
        offset = 0
        for sequence in values:
            notes.extend(replace(note, start=note.start + offset, end=note.end + offset) for note in sequence.notes)
            events.extend(replace(event, time=event.time + offset) for event in sequence.events)
            offset += sequence.duration_ticks
        return cls(tuple(notes), tuple(events), offset, ppqn)


class SequenceBuilder:
    """Mutable construction helper that produces an immutable :class:`Sequence`."""

    __slots__ = ("ticks_per_quarter", "_notes", "_events", "_duration")

    def __init__(self, ticks_per_quarter: int = 24) -> None:
        _integer("ticks_per_quarter", ticks_per_quarter, 1)
        self.ticks_per_quarter = ticks_per_quarter
        self._notes: list[Note] = []
        self._events: list[Event] = []
        self._duration = 0

    def add_note(self, note: Note) -> SequenceBuilder:
        """Append one validated note and return this builder."""

        if not isinstance(note, Note):
            raise ValidationError("add_note expects a Note")
        self._notes.append(note)
        self._duration = max(self._duration, note.end)
        return self

    def add_event(self, event: Event) -> SequenceBuilder:
        """Append one supported timed event and return this builder."""

        if type(event) not in _EVENT_ORDER:
            raise ValidationError("add_event expects a supported timed event")
        self._events.append(event)
        self._duration = max(self._duration, event.time)
        return self

    def set_duration(self, duration_ticks: int) -> SequenceBuilder:
        """Set a duration that contains every value currently in the builder."""

        _integer("duration_ticks", duration_ticks, self._duration)
        self._duration = duration_ticks
        return self

    @property
    def duration_ticks(self) -> int:
        return self._duration

    def build(self) -> Sequence:
        """Construct and return an immutable canonical sequence."""

        return Sequence(tuple(self._notes), tuple(self._events), self._duration, self.ticks_per_quarter)


def bar_spans(sequence: Sequence, *, strict: bool = True) -> tuple[BarSpan, ...]:
    """Return bar intervals through ``sequence.duration_ticks`` in one pass."""

    if not isinstance(sequence, Sequence):
        raise ValidationError("sequence must be a Sequence")
    if not isinstance(strict, bool):
        raise ValidationError("strict must be a boolean")
    signatures = [event for event in sequence.events if isinstance(event, TimeSignature)]
    keys = [event for event in sequence.events if isinstance(event, KeySignature)]
    if not signatures or signatures[0].time != 0:
        signatures.insert(0, TimeSignature(0, 4, 4))
    spans: list[BarSpan] = []
    signature_index = 0
    key_index = 0
    current_key: KeySignature | None = None
    position = 0
    while position < sequence.duration_ticks:
        while signature_index + 1 < len(signatures) and signatures[signature_index + 1].time <= position:
            signature_index += 1
        while key_index < len(keys) and keys[key_index].time <= position:
            current_key = keys[key_index]
            key_index += 1
        signature = signatures[signature_index]
        length_numerator = sequence.ticks_per_quarter * 4 * signature.numerator
        if length_numerator % signature.denominator:
            raise SequenceError("bar length is not integral at this PPQN")
        end = min(sequence.duration_ticks, position + length_numerator // signature.denominator)
        next_change = signatures[signature_index + 1].time if signature_index + 1 < len(signatures) else None
        if next_change is not None and position < next_change < end:
            if strict:
                raise SequenceError(f"time signature changes mid-bar at tick {next_change}")
            end = next_change
        spans.append(
            BarSpan(
                position,
                end,
                replace(signature, time=position),
                None if current_key is None else replace(current_key, time=position),
            )
        )
        position = end
    return tuple(spans)


def _split_sequence_bars(
    sequence: Sequence,
    spans: tuple[BarSpan, ...],
    *,
    carry_context: bool,
) -> tuple[Sequence, ...]:
    """Split one sequence in a single pass over its ordered notes and events."""

    note_index = 0
    event_index = 0
    context_index = 0
    active_notes: list[Note] = []
    latest_tempo: Tempo | None = None
    latest_key: KeySignature | None = None
    channel_state_history: list[ControlChange | ProgramChange] = []
    channel_state_context: tuple[Event, ...] = ()
    channel_state_version = 0
    context_cache: dict[tuple[object, ...], tuple[Event, ...]] = {}
    bars: list[Sequence] = []
    contextual_types = (TimeSignature, KeySignature, Tempo, ProgramChange, ControlChange)
    for span_index, span in enumerate(spans):
        active_notes = [note for note in active_notes if note.end > span.start]
        while note_index < len(sequence.notes) and sequence.notes[note_index].start < span.end:
            note = sequence.notes[note_index]
            if note.end > span.start:
                active_notes.append(note)
            note_index += 1
        notes = tuple(
            Note(
                max(note.start, span.start) - span.start,
                min(note.end, span.end) - span.start,
                note.pitch,
                note.velocity,
                note.channel,
                note.release_velocity,
            )
            for note in active_notes
            if note.start < span.end and note.end > span.start
        )

        while event_index < len(sequence.events) and sequence.events[event_index].time < span.start:
            event_index += 1
        event_end = event_index
        include_end = span_index == len(spans) - 1
        while event_end < len(sequence.events) and (
            sequence.events[event_end].time < span.end or (include_end and sequence.events[event_end].time == span.end)
        ):
            event_end += 1
        events = tuple(replace(event, time=event.time - span.start) for event in sequence.events[event_index:event_end])
        event_index = event_end

        if carry_context:
            channel_state_changed = False
            while context_index < len(sequence.events) and sequence.events[context_index].time <= span.start:
                event = sequence.events[context_index]
                if isinstance(event, Tempo):
                    latest_tempo = event
                elif isinstance(event, KeySignature):
                    latest_key = event
                elif isinstance(event, (ControlChange, ProgramChange)):
                    channel_state_history.append(event)
                    channel_state_changed = True
                context_index += 1
            if channel_state_changed:
                channel_state_context = tuple(replace(event, time=0) for event in channel_state_history)
                channel_state_version += 1

            active_key = span.key_signature or latest_key
            context_key = (
                span.time_signature.numerator,
                span.time_signature.denominator,
                span.time_signature.clocks_per_click,
                span.time_signature.notated_32nd_notes_per_beat,
                active_key.key if active_key is not None else None,
                latest_tempo.microseconds_per_quarter if latest_tempo is not None else None,
                channel_state_version,
            )
            contextual = context_cache.get(context_key)
            if contextual is None:
                contextual_values: list[Event] = [replace(span.time_signature, time=0)]
                if active_key is not None:
                    contextual_values.append(replace(active_key, time=0))
                if latest_tempo is not None:
                    contextual_values.append(replace(latest_tempo, time=0))
                contextual_values.extend(channel_state_context)
                contextual = tuple(contextual_values)
                context_cache[context_key] = contextual
            events = (
                *contextual,
                *(event for event in events if not (event.time == 0 and isinstance(event, contextual_types))),
            )

        bars.append(Sequence(notes, events, span.duration_ticks, sequence.ticks_per_quarter))
    return tuple(bars)


def split_bars(
    sequences: Iterable[Sequence],
    *,
    meta_track_index: int = 0,
    strict: bool = True,
    carry_context: bool = True,
) -> tuple[tuple[Sequence, ...], ...]:
    """Split tracks at the meta track's bars, optionally carrying active state into every bar."""

    raw_sequences: object = sequences
    if isinstance(raw_sequences, (str, bytes)):
        raise ValidationError("sequences must be an iterable of Sequence values")
    try:
        values = tuple(cast(Iterable[Sequence], raw_sequences))
    except TypeError as exc:
        raise ValidationError("sequences must be an iterable of Sequence values") from exc
    if isinstance(meta_track_index, bool) or not isinstance(meta_track_index, int):
        raise ValidationError("meta_track_index must be an integer")
    if not isinstance(strict, bool):
        raise ValidationError("strict must be a boolean")
    if not isinstance(carry_context, bool):
        raise ValidationError("carry_context must be a boolean")
    if not values:
        return ()
    if not all(isinstance(sequence, Sequence) for sequence in values):
        raise ValidationError("sequences must contain Sequence values")
    if not 0 <= meta_track_index < len(values):
        raise SequenceError("meta_track_index is outside the sequence list")
    ppqn = values[meta_track_index].ticks_per_quarter
    if any(sequence.ticks_per_quarter != ppqn for sequence in values):
        raise SequenceError("cannot split bars across sequences with different PPQN")
    duration = max(sequence.duration_ticks for sequence in values)
    padded = tuple(sequence.pad(duration) for sequence in values)
    spans = bar_spans(padded[meta_track_index], strict=strict)
    return tuple(_split_sequence_bars(sequence, spans, carry_context=carry_context) for sequence in padded)
