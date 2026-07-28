"""Deterministic conversion between Mido objects and immutable S-Coda values."""

from __future__ import annotations

import math
from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

import mido

from scoda.core import (
    ControlChange,
    Event,
    KeySignature,
    Note,
    ProgramChange,
    Sequence,
    SequenceBuilder,
    Tempo,
    TimeSignature,
)
from scoda.errors import MidiError, MidiImportError
from scoda.music_theory import Key


@dataclass(frozen=True, slots=True)
class MidiDiagnostic:
    """One deterministic MIDI import observation or repair."""

    code: str
    severity: Literal["warning", "error"]
    track: int
    message_index: int
    tick: int
    details: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code:
            raise MidiError("diagnostic code must be a non-empty string")
        if self.severity not in {"warning", "error"}:
            raise MidiError("diagnostic severity must be 'warning' or 'error'")
        for name in ("track", "message_index", "tick"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise MidiError(f"diagnostic {name} must be a non-negative integer")
        if not isinstance(self.details, str):
            raise MidiError("diagnostic details must be a string")


@dataclass(frozen=True, slots=True)
class MidiImportReport:
    """Immutable summary of a MIDI import and every emitted diagnostic."""

    source_ticks_per_quarter: int
    target_ticks_per_quarter: int
    tracks_read: int
    notes_created: int
    diagnostics: tuple[MidiDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        for name, minimum in (
            ("source_ticks_per_quarter", 1),
            ("target_ticks_per_quarter", 1),
            ("tracks_read", 0),
            ("notes_created", 0),
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise MidiError(f"report {name} must be an integer of at least {minimum}")
        raw_diagnostics: object = self.diagnostics
        if isinstance(raw_diagnostics, (str, bytes)):
            raise MidiError("report diagnostics must be an iterable of MidiDiagnostic values")
        try:
            diagnostics = tuple(cast(Iterable[MidiDiagnostic], raw_diagnostics))
        except TypeError as exc:
            raise MidiError("report diagnostics must be an iterable of MidiDiagnostic values") from exc
        if not all(isinstance(item, MidiDiagnostic) for item in diagnostics):
            raise MidiError("report diagnostics must contain MidiDiagnostic values")
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def repaired(self) -> bool:
        """Return whether malformed information required a deterministic repair."""

        return any(item.severity == "error" for item in self.diagnostics)

    @property
    def lossy(self) -> bool:
        """Return whether any source information was changed or ignored."""

        return bool(self.diagnostics)

    @property
    def warnings(self) -> tuple[MidiDiagnostic, ...]:
        """Return diagnostics for deliberately ignored unsupported information."""

        return tuple(item for item in self.diagnostics if item.severity == "warning")

    @property
    def errors(self) -> tuple[MidiDiagnostic, ...]:
        """Return diagnostics for malformed information or required repairs."""

        return tuple(item for item in self.diagnostics if item.severity == "error")


@dataclass(frozen=True, slots=True)
class MidiLoadResult:
    """Canonical imported sequences together with their complete report."""

    sequences: tuple[Sequence, ...]
    report: MidiImportReport

    def __post_init__(self) -> None:
        raw_sequences: object = self.sequences
        if isinstance(raw_sequences, (str, bytes)):
            raise MidiError("MIDI load result sequences must be an iterable of Sequence values")
        try:
            sequences = tuple(cast(Iterable[Sequence], raw_sequences))
        except TypeError as exc:
            raise MidiError("MIDI load result sequences must be an iterable of Sequence values") from exc
        if not all(isinstance(sequence, Sequence) for sequence in sequences):
            raise MidiError("MIDI load results must contain Sequence values")
        if not isinstance(self.report, MidiImportReport):
            raise MidiError("MIDI load result report must be a MidiImportReport")
        object.__setattr__(self, "sequences", sequences)


@dataclass(frozen=True, slots=True)
class _Record:
    tick: int
    track: int
    index: int
    message: Any = field(compare=False)


@dataclass(frozen=True, slots=True)
class _TimingIssue:
    record: _Record
    details: str


def _scaled(value: int, source_ppqn: int, target_ppqn: int) -> int:
    if source_ppqn == target_ppqn:
        return value
    numerator = value * target_ppqn
    quotient, remainder = divmod(numerator, source_ppqn)
    doubled_remainder = remainder * 2
    if doubled_remainder > source_ppqn or (doubled_remainder == source_ppqn and quotient % 2):
        quotient += 1
    return quotient


def _records(midi_file: mido.MidiFile) -> tuple[list[list[_Record]], list[int], list[_TimingIssue]]:
    records: list[list[_Record]] = []
    durations: list[int] = []
    issues: list[_TimingIssue] = []
    for track_index, track in enumerate(midi_file.tracks):
        tick = 0
        track_records: list[_Record] = []
        for message_index, message in enumerate(track):
            raw_delta = getattr(message, "time", None)
            issue_details = None
            if isinstance(raw_delta, bool) or not isinstance(raw_delta, int):
                if isinstance(raw_delta, float) and math.isfinite(raw_delta):
                    delta = max(0, round(raw_delta))
                else:
                    delta = 0
                issue_details = f"replaced non-integer delta time {raw_delta!r} with {delta}"
            elif raw_delta < 0:
                delta = 0
                issue_details = f"replaced negative delta time {raw_delta} with 0"
            else:
                delta = raw_delta
            tick += delta
            record = _Record(tick, track_index, message_index, message)
            track_records.append(record)
            if issue_details is not None:
                issues.append(_TimingIssue(record, issue_details))
        records.append(track_records)
        durations.append(tick)
    return records, durations, issues


def _reordered_channel_state_records(
    records: Iterable[_Record], source_ppqn: int, target_ppqn: int
) -> tuple[_Record, ...]:
    """Find same-tick channel-state/note order that the immutable model cannot retain."""

    by_tick_channel: dict[tuple[int, int], list[tuple[int, _Record]]] = defaultdict(list)
    for record in records:
        message = record.message
        message_type = getattr(message, "type", None)
        channel = getattr(message, "channel", None)
        if isinstance(channel, bool) or not isinstance(channel, int) or not 0 <= channel <= 15:
            continue
        if message_type in {"control_change", "program_change"}:
            priority = 1
        elif message_type == "note_off":
            velocity = getattr(message, "velocity", None)
            if isinstance(velocity, bool) or not isinstance(velocity, int) or not 0 <= velocity <= 127:
                continue
            priority = 2
        elif message_type == "note_on":
            velocity = getattr(message, "velocity", None)
            if isinstance(velocity, bool) or not isinstance(velocity, int) or not 0 <= velocity <= 127:
                continue
            priority = 2 if velocity == 0 else 3
        else:
            continue
        tick = _scaled(record.tick, source_ppqn, target_ppqn)
        by_tick_channel[(tick, channel)].append((priority, record))

    reordered = []
    for values in by_tick_channel.values():
        priorities = [priority for priority, _ in values]
        if 1 in priorities and any(priority > 1 for priority in priorities) and priorities != sorted(priorities):
            maximum_priority = -1
            for priority, record in values:
                if priority < maximum_priority:
                    reordered.append(record)
                    break
                maximum_priority = max(maximum_priority, priority)
    return tuple(reordered)


def load_midi(
    source: str | Path | mido.MidiFile,
    *,
    track_groups: Iterable[Iterable[int]] | None = None,
    meta_track_indices: Iterable[int] | None = None,
    meta_target: int = 0,
    target_ticks_per_quarter: int | None = None,
    mode: Literal["repair", "strict", "lossless"] = "repair",
) -> MidiLoadResult:
    """Load MIDI into canonical sequences and return all repairs as diagnostics."""

    if mode not in {"repair", "strict", "lossless"}:
        raise MidiError("mode must be 'repair', 'strict', or 'lossless'")
    midi_file = source if isinstance(source, mido.MidiFile) else mido.MidiFile(source)
    if isinstance(midi_file.type, bool) or midi_file.type not in {0, 1, 2}:
        raise MidiError(f"invalid MIDI format: {midi_file.type!r}")
    if midi_file.type == 2:
        raise MidiError("MIDI format 2 is not supported because its tracks have independent timelines")
    if midi_file.type == 0 and len(midi_file.tracks) != 1:
        raise MidiError("MIDI format 0 must contain exactly one track")
    source_ppqn = midi_file.ticks_per_beat
    if isinstance(source_ppqn, bool) or not isinstance(source_ppqn, int) or source_ppqn <= 0:
        raise MidiError("source MIDI ticks_per_beat must be a positive integer")
    target_ppqn = source_ppqn if target_ticks_per_quarter is None else target_ticks_per_quarter
    if isinstance(target_ppqn, bool) or not isinstance(target_ppqn, int) or target_ppqn <= 0:
        raise MidiError("target_ticks_per_quarter must be a positive integer")
    grouped_records, track_durations, timing_issues = _records(midi_file)
    if track_groups is None:
        groups: tuple[tuple[int, ...], ...] = tuple((index,) for index in range(len(midi_file.tracks)))
    else:
        try:
            groups = tuple(tuple(group) for group in track_groups)
        except TypeError as exc:
            raise MidiError("track_groups must be an iterable of track-index iterables") from exc
    if not groups:
        raise MidiError("track_groups must contain at least one group")
    if any(not group for group in groups):
        raise MidiError("track_groups may not contain empty groups")
    if any(isinstance(index, bool) or not isinstance(index, int) for group in groups for index in group):
        raise MidiError("track_groups indices must be integers")
    all_indices = {index for group in groups for index in group}
    if any(index < 0 or index >= len(midi_file.tracks) for index in all_indices):
        raise MidiError("track_groups contains an invalid MIDI track index")
    if len(all_indices) != sum(len(group) for group in groups):
        raise MidiError("a MIDI track may not appear in more than one track group")
    if isinstance(meta_target, bool) or not isinstance(meta_target, int) or not 0 <= meta_target < len(groups):
        raise MidiError("meta_target is outside track_groups")
    try:
        meta_indices = set(range(len(midi_file.tracks))) if meta_track_indices is None else set(meta_track_indices)
    except TypeError as exc:
        raise MidiError("meta_track_indices must be an iterable of hashable integers") from exc
    if any(isinstance(index, bool) or not isinstance(index, int) for index in meta_indices):
        raise MidiError("meta_track_indices must contain integers")
    if any(index < 0 or index >= len(midi_file.tracks) for index in meta_indices):
        raise MidiError("meta_track_indices contains an invalid MIDI track index")

    diagnostics: list[MidiDiagnostic] = []
    builders = [SequenceBuilder(target_ppqn) for _ in groups]
    notes_created = 0

    def diagnostic(record: _Record, code: str, severity: Literal["warning", "error"], details: str) -> None:
        diagnostics.append(
            MidiDiagnostic(
                code,
                severity,
                record.track,
                record.index,
                _scaled(record.tick, source_ppqn, target_ppqn),
                details,
            )
        )

    for issue in timing_issues:
        diagnostic(issue.record, "invalid_delta_time", "error", issue.details)

    if target_ppqn != source_ppqn:
        for track_records in grouped_records:
            for record in track_records:
                if record.tick * target_ppqn % source_ppqn:
                    diagnostic(
                        record,
                        "quantized_tick",
                        "warning",
                        f"rounded source tick {record.tick} to target tick "
                        f"{_scaled(record.tick, source_ppqn, target_ppqn)}",
                    )

    for group_index, group in enumerate(groups):
        records = sorted(
            (record for track_index in group for record in grouped_records[track_index]),
            key=lambda record: (record.tick, record.track, record.index),
        )
        for record in _reordered_channel_state_records(records, source_ppqn, target_ppqn):
            diagnostic(
                record,
                "reordered_same_tick_channel_state",
                "error",
                "canonical export places same-channel program/control changes before note messages at the same tick",
            )
        duration = _scaled(max((track_durations[index] for index in group), default=0), source_ppqn, target_ppqn)
        active: dict[tuple[int, int], deque[tuple[int, int, _Record]]] = defaultdict(deque)
        for record in records:
            message = record.message
            tick = _scaled(record.tick, source_ppqn, target_ppqn)
            try:
                if message.type in {"note_on", "note_off"}:
                    for name, minimum, maximum in (("channel", 0, 15), ("note", 0, 127), ("velocity", 0, 127)):
                        value = getattr(message, name)
                        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
                            raise ValueError(f"{name} must be an integer from {minimum} to {maximum}")
                if message.type == "note_on" and message.velocity > 0:
                    queue = active[(message.channel, message.note)]
                    if queue:
                        diagnostic(
                            record,
                            "overlapping_note_on",
                            "error",
                            "truncated the active same-channel/pitch note at the retrigger",
                        )
                        while queue:
                            start, velocity, start_record = queue.popleft()
                            if tick > start:
                                builders[group_index].add_note(
                                    Note(start, tick, message.note, velocity, message.channel, 0)
                                )
                                notes_created += 1
                            else:
                                diagnostic(
                                    start_record,
                                    "zero_length_retriggered_note",
                                    "error",
                                    "discarded a retriggered note with non-positive duration",
                                )
                    queue.append((tick, message.velocity, record))
                elif message.type == "note_off" or (message.type == "note_on" and message.velocity == 0):
                    queue = active[(message.channel, message.note)]
                    if not queue:
                        diagnostic(record, "unmatched_note_off", "error", "discarded note-off without an active note")
                        continue
                    start, velocity, start_record = queue.popleft()
                    if tick <= start:
                        diagnostic(record, "zero_length_note", "error", "discarded note with non-positive duration")
                        continue
                    release_velocity = message.velocity if message.type == "note_off" else 0
                    builders[group_index].add_note(
                        Note(start, tick, message.note, velocity, message.channel, release_velocity)
                    )
                    notes_created += 1
                elif message.type == "control_change":
                    builders[group_index].add_event(
                        ControlChange(tick, message.control, message.value, message.channel)
                    )
                elif message.type == "program_change":
                    builders[group_index].add_event(ProgramChange(tick, message.program, message.channel))
                elif not message.is_meta:
                    diagnostic(
                        record, "unsupported_channel_message", "warning", f"ignored MIDI message {message.type!r}"
                    )
            except (AttributeError, TypeError, ValueError) as exc:
                diagnostic(record, "invalid_message", "error", f"discarded invalid message: {exc}")
        for (channel, pitch), queue in active.items():
            while queue:
                start, velocity, start_record = queue.popleft()
                source_track_end = _scaled(
                    track_durations[start_record.track],
                    source_ppqn,
                    target_ppqn,
                )
                if source_track_end <= start:
                    diagnostic(
                        start_record, "zero_length_unclosed_note", "error", "discarded unclosed note at track end"
                    )
                    continue
                builders[group_index].add_note(Note(start, source_track_end, pitch, velocity, channel, 0))
                notes_created += 1
                diagnostic(start_record, "unclosed_note", "error", "closed active note at track end")
        builders[group_index].set_duration(max(duration, builders[group_index].duration_ticks))

    meta_records = sorted(
        (record for track_index in meta_indices for record in grouped_records[track_index]),
        key=lambda record: (record.tick, record.track, record.index),
    )
    for record in meta_records:
        message = record.message
        tick = _scaled(record.tick, source_ppqn, target_ppqn)
        try:
            if message.type == "time_signature":
                builders[meta_target].add_event(
                    TimeSignature(
                        tick,
                        message.numerator,
                        message.denominator,
                        message.clocks_per_click,
                        message.notated_32nd_notes_per_beat,
                    )
                )
            elif message.type == "key_signature":
                builders[meta_target].add_event(KeySignature(tick, Key(message.key)))
            elif message.type == "set_tempo":
                builders[meta_target].add_event(Tempo(tick, message.tempo))
            elif message.is_meta and message.type != "end_of_track":
                diagnostic(record, "unsupported_meta_message", "warning", f"ignored MIDI meta message {message.type!r}")
        except (AttributeError, TypeError, ValueError) as exc:
            diagnostic(record, "invalid_meta_message", "error", f"discarded invalid meta message: {exc}")

    sequences = tuple(builder.build() for builder in builders)
    report = MidiImportReport(source_ppqn, target_ppqn, len(midi_file.tracks), notes_created, tuple(diagnostics))
    violations = report.errors if mode == "strict" else report.diagnostics if mode == "lossless" else ()
    if violations:
        first = violations[0]
        raise MidiImportError(
            f"{mode} MIDI import failed with {len(violations)} diagnostic(s); "
            f"first: {first.code} at track {first.track}, tick {first.tick}",
            report,
        )
    return MidiLoadResult(sequences, report)


def _mido_event(event: Event) -> Any:
    if isinstance(event, TimeSignature):
        return mido.MetaMessage(
            "time_signature",
            numerator=event.numerator,
            denominator=event.denominator,
            clocks_per_click=event.clocks_per_click,
            notated_32nd_notes_per_beat=event.notated_32nd_notes_per_beat,
            time=0,
        )
    if isinstance(event, KeySignature):
        return mido.MetaMessage("key_signature", key=event.key.value, time=0)
    if isinstance(event, Tempo):
        return mido.MetaMessage("set_tempo", tempo=event.microseconds_per_quarter, time=0)
    if isinstance(event, ControlChange):
        return mido.Message("control_change", channel=event.channel, control=event.control, value=event.value, time=0)
    if isinstance(event, ProgramChange):
        return mido.Message("program_change", channel=event.channel, program=event.program, time=0)
    raise MidiError(f"unsupported event: {event!r}")


def to_mido(
    sequences: Iterable[Sequence],
    *,
    meta_source: int = 0,
    track_names: Iterable[str | None] | None = None,
) -> mido.MidiFile:
    """Convert canonical sequences to a deterministic Mido file."""

    raw_sequences: object = sequences
    if isinstance(raw_sequences, (str, bytes)):
        raise MidiError("sequences must be an iterable of Sequence values")
    try:
        values = tuple(cast(Iterable[Sequence], raw_sequences))
    except TypeError as exc:
        raise MidiError("sequences must be an iterable of Sequence values") from exc
    if not values:
        raise MidiError("at least one sequence is required")
    if not all(isinstance(sequence, Sequence) for sequence in values):
        raise MidiError("sequences must contain Sequence values")
    ppqn = values[0].ticks_per_quarter
    if any(sequence.ticks_per_quarter != ppqn for sequence in values):
        raise MidiError("cannot save sequences with different PPQN")
    if ppqn > 0x7FFF:
        raise MidiError("MIDI ticks per quarter must not exceed 32767")
    if isinstance(meta_source, bool) or not isinstance(meta_source, int) or not 0 <= meta_source < len(values):
        raise MidiError("meta_source is outside the sequence list")
    if isinstance(track_names, (str, bytes)):
        raise MidiError("track_names must be an iterable of strings or None, not a string")
    try:
        names = tuple(track_names) if track_names is not None else (None,) * len(values)
    except TypeError as exc:
        raise MidiError("track_names must be an iterable of strings or None") from exc
    if len(names) != len(values):
        raise MidiError("track_names must match the number of sequences")
    if any(name is not None and not isinstance(name, str) for name in names):
        raise MidiError("track_names entries must be strings or None")
    try:
        for name in names:
            if name is not None:
                name.encode("latin1")
    except UnicodeEncodeError as exc:
        raise MidiError("track_names must contain only characters representable in MIDI Latin-1 text") from exc
    midi_file = mido.MidiFile(ticks_per_beat=ppqn)
    for sequence_index, sequence in enumerate(values):
        active_until: dict[tuple[int, int], int] = {}
        for note in sequence.notes:
            key = (note.channel, note.pitch)
            if note.start < active_until.get(key, -1):
                raise MidiError(
                    "cannot export overlapping notes with the same channel and pitch: "
                    f"sequence={sequence_index}, channel={note.channel}, pitch={note.pitch}, tick={note.start}"
                )
            active_until[key] = note.end
        records: list[tuple[int, int, Any]] = []
        if names[sequence_index] is not None:
            records.append((0, 0, mido.MetaMessage("track_name", name=names[sequence_index], time=0)))
        for event in sequence.events:
            is_global = isinstance(event, (TimeSignature, KeySignature, Tempo))
            if is_global and sequence_index != meta_source:
                continue
            records.append((event.time, 0 if is_global else 1, _mido_event(event)))
        for note in sequence.notes:
            records.append(
                (
                    note.end,
                    2,
                    mido.Message(
                        "note_off",
                        note=note.pitch,
                        velocity=note.release_velocity,
                        channel=note.channel,
                        time=0,
                    ),
                )
            )
            records.append(
                (
                    note.start,
                    3,
                    mido.Message("note_on", note=note.pitch, velocity=note.velocity, channel=note.channel, time=0),
                )
            )
        records.sort(key=lambda item: (item[0], item[1], getattr(item[2], "channel", -1), getattr(item[2], "note", -1)))
        track = mido.MidiTrack()
        previous = 0
        for tick, _, message in records:
            track.append(message.copy(time=tick - previous))
            previous = tick
        track.append(mido.MetaMessage("end_of_track", time=sequence.duration_ticks - previous))
        midi_file.tracks.append(track)
    return midi_file


def save_midi(
    sequences: Iterable[Sequence],
    destination: str | Path,
    *,
    meta_source: int = 0,
    track_names: Iterable[str | None] | None = None,
) -> None:
    """Write canonical sequences to a deterministic standard MIDI file."""

    to_mido(sequences, meta_source=meta_source, track_names=track_names).save(destination)
