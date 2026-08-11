import importlib
import inspect
import json
import math
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import mido
import pytest

import scoda
from scoda import (
    BarSpan,
    ControlChange,
    Key,
    KeySignature,
    MidiDiagnostic,
    MidiError,
    MidiImportError,
    MidiImportReport,
    MidiLoadResult,
    Note,
    NotelikeConfig,
    NotelikeTokeniser,
    ProgramChange,
    Sequence,
    SequenceBuilder,
    SequenceError,
    Tempo,
    TimeSignature,
    TokenisationError,
    TokeniserState,
    TokenMetadata,
    ValidationError,
    VocabularyManifest,
    bar_spans,
    create_tokeniser,
    load_midi,
    save_midi,
    split_bars,
    to_mido,
)
from scoda.midi_io import _mido_event, _scaled
from scoda.tokenisation.tokeniser import _manifest


def test_public_api_exports_and_key_signatures_are_frozen():
    assert scoda.__all__ == [
        "BarSpan",
        "ControlChange",
        "Event",
        "KeySignature",
        "Key",
        "MidiDiagnostic",
        "MidiError",
        "MidiImportError",
        "MidiImportReport",
        "MidiLoadResult",
        "Note",
        "NotelikeConfig",
        "NotelikeTokeniser",
        "ProgramChange",
        "ScodaError",
        "Sequence",
        "SequenceBuilder",
        "SequenceError",
        "Tempo",
        "TimeSignature",
        "TokenisationError",
        "TokeniserState",
        "TokenMetadata",
        "ValidationError",
        "VocabularyManifest",
        "bar_spans",
        "create_tokeniser",
        "load_midi",
        "save_midi",
        "split_bars",
        "to_mido",
    ]
    expected_parameters = {
        Note: ("start", "end", "pitch", "velocity", "channel", "release_velocity"),
        Sequence: ("notes", "events", "duration_ticks", "ticks_per_quarter"),
        NotelikeConfig: (
            "ticks_per_quarter",
            "num_tracks",
            "pitch_range",
            "note_values",
            "velocity_bins",
            "include_time_signatures",
            "max_bar_quarters",
        ),
        NotelikeTokeniser: ("config",),
        create_tokeniser: ("codec_id", "config"),
        load_midi: (
            "source",
            "track_groups",
            "meta_track_indices",
            "meta_target",
            "target_ticks_per_quarter",
            "mode",
        ),
        save_midi: ("sequences", "destination", "meta_source", "track_names"),
        split_bars: ("sequences", "meta_track_index", "strict", "carry_context"),
    }
    for callable_value, parameters in expected_parameters.items():
        assert tuple(inspect.signature(callable_value).parameters) == parameters


@pytest.mark.parametrize(
    "module_name",
    (
        "scoda.elements.message",
        "scoda.midi.midi_file",
        "scoda.misc.music_theory",
        "scoda.sequences.sequence",
        "scoda.tokenisation.notelike_tokenisation",
    ),
)
def test_removed_module_paths_do_not_import(module_name):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


@pytest.mark.parametrize(
    ("factory", "arguments"),
    [
        (Note, (0, 1, 60, 100, True)),
        (TimeSignature, (0, 4, 3)),
        (KeySignature, (0, "not-a-key")),
        (Tempo, (0, 0)),
        (ControlChange, (0, 128, 0, 0)),
        (ControlChange, (0, 1, 128, 0)),
        (ProgramChange, (0, 128, 0)),
    ],
)
def test_value_validation(factory, arguments):
    with pytest.raises(ValidationError):
        factory(*arguments)


def test_sequence_construction_properties_and_transformations():
    events = (
        ControlChange(4, 64, 127, 2),
        ProgramChange(0, 10, 2),
        Tempo(0, 500_000),
        KeySignature(0, "C"),
        TimeSignature(0, 4, 4),
    )
    sequence = Sequence((Note(5, 10, 62, 80, 2), Note(0, 4, 60, 40, 2)), events, 12, 24)

    assert sequence.duration_ticks == 12
    assert sequence.channel == 2
    assert not sequence.is_empty()
    assert sequence.duration_relation(Sequence()) == float("inf")
    assert Sequence().duration_relation(Sequence()) == 1.0
    assert sequence.duration_relation(Sequence(duration_ticks=6)) == 2.0
    with pytest.raises(ValidationError):
        sequence.duration_relation(object())
    with pytest.raises(ValidationError):
        sequence.similarity(object())

    changed = sequence.with_channel(3).with_velocity(lambda velocity: velocity + 1)
    assert changed.channel == 3
    assert [note.velocity for note in changed.notes] == [41, 81]
    assert changed.with_velocity(70).notes[0].velocity == 70
    with pytest.raises(ValidationError):
        changed.with_velocity(0)
    assert len(sequence.filter_events(lambda event: isinstance(event, Tempo)).events) == 1
    assert sequence.pad(10) is sequence
    assert sequence.pad(20).duration_ticks == 20
    assert sequence.cutoff(20) is sequence
    assert sequence.pad(20).cutoff(15, 8).duration_ticks == 8

    similar = Sequence((Note(0, 4, 60, 99, 7),), (ProgramChange(0, 10, 2),), 4, 24)
    assert sequence.similarity(similar, compare_velocity=False, compare_channel=False) > 0
    assert sequence.similarity(similar, compare_velocity=True, compare_channel=True) == 0.5
    assert (
        Sequence(events=(ProgramChange(0, 4, 1),)).similarity(
            Sequence(events=(ProgramChange(0, 4, 2),)), compare_channel=False
        )
        == 1.0
    )
    assert Sequence().similarity(Sequence()) == 1.0
    program_only = Sequence((), (ProgramChange(0, 10),), 0, 24)
    assert program_only.similarity(program_only) == 1.0


def test_sequence_validation_transpose_quantise_resample_and_slice():
    with pytest.raises(ValidationError):
        Sequence(("note",), (), 1)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        Sequence((), ("event",), 1)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        Sequence((Note(0, 2, 60, 80),), (), 1)

    source = Sequence(
        (Note(1, 2, 0, 80), Note(4, 7, 127, 90)),
        (KeySignature(0, Key.C), Tempo(3, 400_000)),
        9,
        24,
    )
    assert [note.pitch for note in source.transpose(1, out_of_range="drop").notes] == [1]
    assert [note.pitch for note in source.transpose(1, out_of_range="octave_wrap").notes] == [1, 116]
    assert source.transpose(12, out_of_range="octave_wrap").events[0].key == Key.C
    assert source.transpose(-1, out_of_range="octave_wrap").notes[0].pitch == 11
    with pytest.raises(SequenceError):
        source.transpose(1)
    with pytest.raises(SequenceError):
        source.transpose(-1, out_of_range="octave_wrap", pitch_range=(0, 5))
    with pytest.raises(ValueError):
        source.transpose(1, out_of_range="unknown")  # type: ignore[arg-type]

    for invalid in ((), (0,), (True,)):
        with pytest.raises(ValidationError):
            source.quantise(invalid)
        with pytest.raises(ValidationError):
            source.quantise_note_lengths(invalid)
    quantised = source.quantise((3, 4))
    assert quantised.notes[0].end > quantised.notes[0].start
    assert source.quantise_note_lengths((2, 4)).notes[1].end == 6
    assert source.quantise_and_normalise((2,), (4,)).notes[0] == Note(0, 4, 0, 80)

    empty = Sequence(duration_ticks=5)
    assert empty.quantise((2,)).duration_ticks == 4
    assert empty.quantise_note_lengths((2, 4)) == empty
    assert empty.quantise_and_normalise((2,), (4,)).duration_ticks == 4

    assert source.resample(24) is source
    assert source.resample(1).notes[0].end == 1
    assert source.slice(1, 5).duration_ticks == 4
    with pytest.raises(SequenceError):
        source.slice(0, 10)
    assert [part.duration_ticks for part in source.split((3, 3))] == [3, 3, 3]
    assert source.split((99,))[0] == source
    with pytest.raises(ValidationError):
        source.split((0,))


def test_sequence_composition_builder_and_bars():
    empty = Sequence.merge(())
    assert empty == Sequence.concatenate(()) == Sequence()
    first = Sequence((Note(0, 2, 60, 80),), (), 4, 24)
    second = Sequence((Note(1, 3, 64, 90),), (), 4, 24)
    assert len(Sequence.merge((first, second)).notes) == 2
    assert Sequence.concatenate((first, second)).notes[-1].start == 5
    mismatched = Sequence((), (), 1, 48)
    with pytest.raises(SequenceError):
        Sequence.merge((first, mismatched))
    with pytest.raises(SequenceError):
        Sequence.concatenate((first, mismatched))

    builder = SequenceBuilder(24)
    note = Note(0, 2, 60, 80)
    assert builder.add_note(note).add_event(Tempo(0, 500_000)).set_duration(4) is builder
    assert builder.duration_ticks == 4
    assert builder.build().notes == (note,)
    with pytest.raises(ValidationError):
        builder.add_note("note")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        builder.add_event("event")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        builder.set_duration(1)

    meta = Sequence(
        (),
        (TimeSignature(0, 4, 4), KeySignature(0, Key.C), TimeSignature(96, 3, 4)),
        168,
        24,
    )
    spans = bar_spans(meta)
    assert [(span.start, span.end, span.duration_ticks) for span in spans] == [(0, 96, 96), (96, 168, 72)]
    assert spans[0].key_signature is not None
    with pytest.raises(ValidationError):
        BarSpan(0, 96, TimeSignature(1, 4, 4))
    with pytest.raises(ValidationError):
        BarSpan(0, 96, TimeSignature(0, 4, 4), KeySignature(1, Key.C))
    contextual_bars = split_bars((meta, first), strict=True)
    assert len(contextual_bars) == 2
    assert contextual_bars[0][0].events == (
        TimeSignature(0, 4, 4),
        KeySignature(0, Key.C),
    )
    assert contextual_bars[0][1].events == (
        TimeSignature(0, 3, 4),
        KeySignature(0, Key.C),
    )
    assert contextual_bars[0][1].events == contextual_bars[1][1].events
    assert split_bars((meta,), carry_context=False)[0][1].events == (TimeSignature(0, 3, 4),)
    assert split_bars(()) == ()
    with pytest.raises(SequenceError):
        split_bars((meta,), meta_track_index=1)
    non_integral = Sequence((), (TimeSignature(0, 1, 8),), 1, 1)
    with pytest.raises(SequenceError):
        bar_spans(non_integral)
    mid_bar = Sequence((), (TimeSignature(24, 3, 4),), 96, 24)
    assert bar_spans(mid_bar, strict=False)[0].end == 24


@pytest.mark.parametrize(
    "overrides",
    [
        {"ticks_per_quarter": True},
        {"num_tracks": 0},
        {"velocity_bins": 0},
        {"max_bar_quarters": False},
        {"max_bar_quarters": 65},
        {"ticks_per_quarter": 32768},
        {"include_time_signatures": 1},
        {"note_values": ()},
        {"note_values": (True,)},
        {"note_values": (3, 3)},
        {"note_values": (0x10000000,)},
        {"pitch_range": (0, 127), "note_values": tuple(range(1, 129)), "velocity_bins": 127},
        {"velocity_bins": 128},
        {"pitch_range": (-1, 127)},
        {"pitch_range": (0, True)},
    ],
)
def test_notelike_config_is_strict(overrides):
    with pytest.raises(TokenisationError):
        NotelikeConfig(**overrides)


def test_key_names_and_transposition_are_explicit():
    assert Key.F_SHARP.value == "F#"
    assert Key.B_FLAT_MINOR.value == "Bbm"
    assert Key.D_FLAT.transpose(0) is Key.C_SHARP
    assert Key.A_MINOR.transpose(2) is Key.B_MINOR
    with pytest.raises(ValidationError):
        Key.C.transpose(True)


def test_token_metadata_is_immutable_normalised_and_validated():
    metadata = TokenMetadata([0], [0], [0], [0], [None], [math.nan], [math.nan])  # type: ignore[arg-type]
    assert metadata.token_index == (0,)
    assert len(metadata) == 1
    with pytest.raises(TokenisationError, match="equal lengths"):
        TokenMetadata((0,), (), (0,), (0,), (None,), (math.nan,), (math.nan,))
    with pytest.raises(TokenisationError):
        TokenMetadata((0,), (0,), (0,), (0,), (None,), (10**1000,), (math.nan,))
    for arguments in (
        ((-1,), (0,), (0,), (0,), (None,), (math.nan,), (math.nan,)),
        ((0,), (0,), (0,), (0,), (-1,), (math.nan,), (math.nan,)),
        ((0,), (0,), (0,), (0,), (None,), (128,), (math.nan,)),
        ((0,), (0,), (0,), (0,), (None,), (math.nan,), (7,)),
    ):
        with pytest.raises(TokenisationError):
            TokenMetadata(*arguments)


def test_tokeniser_manifest_codec_and_state_machine():
    tokeniser = NotelikeTokeniser(
        NotelikeConfig(num_tracks=2, pitch_range=(60, 64), note_values=(3, 6), velocity_bins=2)
    )
    assert tokeniser.vocabulary_size == tokeniser.manifest.size
    assert tokeniser.vocabulary == tokeniser.manifest.tokens
    assert tokeniser.manifest.normalised_config["num_tracks"] == 2
    assert tokeniser.start_token_id == tokeniser.token_to_id["sta"]
    assert tokeniser.stop_token_id == tokeniser.token_to_id["sto"]
    with pytest.raises(TokenisationError):
        tokeniser.encode(["missing"])
    with pytest.raises(TokenisationError):
        tokeniser.decode([-1])
    for invalid_id in (True, 1.5, "1"):
        with pytest.raises(TokenisationError):
            tokeniser.decode([invalid_id])  # type: ignore[list-item]
    with pytest.raises(TypeError):
        tokeniser.token_to_id["new"] = 123  # type: ignore[index]

    note_values = [3, 6]
    normalised = NotelikeConfig(note_values=note_values)  # type: ignore[arg-type]
    note_values.append(12)
    assert normalised.note_values == (3, 6)

    source = (
        Sequence((Note(0, 3, 60, 20), Note(24, 30, 64, 120)), (), 96, 24),
        Sequence((Note(0, 6, 62, 70, 1),), (), 96, 24),
    )
    tokens = tokeniser.tokenise(source)
    assert tokeniser.decode(tokeniser.encode(tokens)) == tokens
    result = tokeniser.detokenise(tokens)
    assert [len(sequence.notes) for sequence in result] == [2, 1]
    metadata = tokeniser.metadata(tokens)
    assert len(metadata) == len(tokens)
    assert 64 in metadata.pitch
    with pytest.raises(TokenisationError):
        tokeniser.tokenise(source[:1])
    with pytest.raises(TokenisationError):
        tokeniser.tokenise((source[0], Sequence((), (), 96, 48)))

    initial = tokeniser.initial_state()
    assert tokeniser.token_to_id["sta"] in tokeniser.allowed_token_ids(initial)
    started = tokeniser.advance(initial, tokeniser.start_token_id)
    allowed = tokeniser.allowed_token_ids(started)
    assert tokeniser.token_to_id["bar"] in allowed
    assert tokeniser.token_to_id["trk_00"] in allowed
    completed_bar = tokeniser.advance(started, tokeniser.token_to_id["bar"])
    assert completed_bar.bar_count == 1
    assert tokeniser.token_to_id["trk_00"] in tokeniser.allowed_token_ids(completed_bar)
    assert tokeniser.inspect_prefix(tokeniser.encode(tokens)).ended
    with pytest.raises(TokenisationError):
        tokeniser.advance(TokeniserState(valid=False), tokeniser.start_token_id)
    with pytest.raises(TokenisationError):
        tokeniser.advance(initial, -1)
    with pytest.raises(TokenisationError):
        tokeniser.detokenise(["sta", "pit_060-val_03-vel_032"])
    with pytest.raises(TokenisationError):
        tokeniser.detokenise(["sta", "bar", "trk_00", "pit_060-val_99-vel_032", "sto"])
    with pytest.raises(TokenisationError):
        tokeniser.metadata(["sta", "missing"])


@pytest.mark.parametrize(
    "tokens",
    [
        ["sta", "trk_00", "pit_060-val_03-vel_064", "sto"],
        ["sta", "bar", "trk_00", "pit_060-val_03-vel_064", "sto"],
        ["sta", "pos_095", "trk_00", "pit_060-val_03-vel_064", "sto"],
    ],
)
def test_strict_grammar_rejects_noncanonical_streams(tokens):
    tokeniser = NotelikeTokeniser(NotelikeConfig(pitch_range=(60, 60), note_values=(3,)))

    with pytest.raises(TokenisationError):
        tokeniser.detokenise(tokens)


def test_canonical_roundtrip_and_body_metadata_alignment():
    tokeniser = NotelikeTokeniser(NotelikeConfig(pitch_range=(60, 64), note_values=(12,)))
    source = Sequence(
        (Note(0, 12, 60, 127), Note(108, 120, 64, 127)),
        (),
        192,
        24,
    )

    tokens = tokeniser.tokenise((source,))
    assert tokeniser.tokenise(tokeniser.detokenise(tokens)) == tokens
    body = tokeniser.unframe(tokens)
    metadata = tokeniser.body_metadata(body)
    assert isinstance(metadata, TokenMetadata)
    assert len(metadata) == len(body)
    second_bar = [index for index, token in enumerate(body) if token == "bar"][1]
    assert metadata.track_index[second_bar] is None


def test_tokenisation_normalisation_policy_is_stable():
    tokeniser = NotelikeTokeniser(
        NotelikeConfig(
            pitch_range=(60, 60),
            note_values=(6, 12),
            velocity_bins=2,
            include_time_signatures=True,
        )
    )
    source = Sequence(
        (Note(0, 10, 60, 80, 7, 45),),
        (TimeSignature(0, 4, 4, 36, 12), Tempo(0, 500_000), ProgramChange(0, 4, 7)),
        12,
        24,
    )

    restored = tokeniser.detokenise(tokeniser.tokenise((source,)))[0]

    assert restored.notes == (Note(0, 12, 60, 95, 0, 0),)
    assert restored.events == (TimeSignature(0, 4, 4),)


def test_metadata_value_imputation_is_explicit():
    tokeniser = NotelikeTokeniser(NotelikeConfig(pitch_range=(60, 60), note_values=(3,)))
    note_token = next(token for token in tokeniser.vocabulary if token.startswith("pit_"))
    tokens = ["sta", "trk_00", note_token, "bar", "sto"]

    sparse = tokeniser.metadata(tokens)
    imputed = tokeniser.metadata(tokens, impute_pitch=True)
    assert math.isnan(sparse.pitch[0])
    assert imputed.pitch[:2] == (69, 69)
    assert imputed.pitch[-1] == 60
    with pytest.raises(TokenisationError):
        tokeniser.metadata(tokens, impute_pitch=1)  # type: ignore[arg-type]


def test_tokeniser_collection_and_public_value_validation():
    tokeniser = NotelikeTokeniser(NotelikeConfig())
    for operation in (tokeniser.frame, tokeniser.encode, tokeniser.detokenise):
        with pytest.raises(TokenisationError):
            operation("sta")
    with pytest.raises(TokenisationError):
        tokeniser.tokenise_body("sequence")
    with pytest.raises(TokenisationError):
        VocabularyManifest("codec", "{}", "sta", "bad")  # type: ignore[arg-type]
    for state in (
        {"started": True},
        {"ended": True},
        {"phase": "started"},
        {"bar_position": 97},
    ):
        with pytest.raises(TokenisationError):
            TokeniserState(**state)
    with pytest.raises(MidiError):
        MidiDiagnostic("", "warning", 0, 0, 0, "")
    with pytest.raises(MidiError):
        MidiImportReport(24, 24, 1, 0, ("bad",))  # type: ignore[arg-type]
    with pytest.raises(MidiError):
        MidiLoadResult(("bad",), MidiImportReport(24, 24, 1, 0))  # type: ignore[arg-type]


def test_manifest_state_and_incremental_api_validation_branches():
    manifest_arguments = [
        ("", "{}", (), "bad"),
        ("codec", 1, (), "bad"),
        ("codec", "{", (), "bad"),
        ("codec", "[]", (), "bad"),
        ("codec", "{}", ("",), "bad"),
        ("codec", "{}", ("sta", "sta"), "bad"),
        ("codec", "{}", ("sta",), "bad"),
    ]
    for arguments in manifest_arguments:
        with pytest.raises(TokenisationError):
            VocabularyManifest(*arguments)  # type: ignore[arg-type]
    with pytest.raises(TokenisationError):
        _manifest("codec", {}, ("sta", "sta"))
    with pytest.raises(TokenisationError):
        _manifest("codec", {"invalid": float("nan")}, ())
    canonical_manifest = _manifest("codec", {"b": 2, "a": 1}, ("sta",))
    reconstructed_manifest = VocabularyManifest(
        canonical_manifest.codec_id,
        json.dumps({"b": 2, "a": 1}, indent=2),
        canonical_manifest.tokens,
        canonical_manifest.sha256,
    )
    assert reconstructed_manifest == canonical_manifest

    invalid_states = [
        {"started": 1},
        {"active_track": True},
        {"active_track": -1},
        {"bar_count": True},
        {"bar_capacity": 0},
        {"phase": "invalid"},
        {"started": True, "phase": "ended"},
        {"last_note_key": [1, 2, 3]},
        {"last_note_key": 1},
    ]
    for arguments in invalid_states:
        with pytest.raises(TokenisationError):
            TokeniserState(**arguments)  # type: ignore[arg-type]

    class BrokenIterable:
        def __iter__(self):
            raise TypeError("broken")

    tokeniser = NotelikeTokeniser(NotelikeConfig(num_tracks=1))
    assert tokeniser.state_key(tokeniser.initial_state()) == tokeniser.state_key(tokeniser.initial_state())
    for values in (1, BrokenIterable(), [1]):
        with pytest.raises(TokenisationError):
            tokeniser.encode(values)  # type: ignore[arg-type]
    for state, token_id in (
        (object(), tokeniser.start_token_id),
        (TokeniserState(active_track=1), tokeniser.start_token_id),
        (tokeniser.initial_state(), True),
        (tokeniser.initial_state(), 1.5),
        (tokeniser.initial_state(), 999_999),
    ):
        with pytest.raises(TokenisationError):
            tokeniser.advance(state, token_id)  # type: ignore[arg-type]
    with pytest.raises(TokenisationError):
        tokeniser.allowed_token_ids(object())  # type: ignore[arg-type]
    with pytest.raises(TokenisationError):
        tokeniser.state_key(object())  # type: ignore[arg-type]

    tokeniser._allowed_token_cache.clear()
    tokeniser._allowed_token_cache_limit = 1
    tokeniser.allowed_token_ids(tokeniser.initial_state())
    tokeniser.allowed_token_ids(TokeniserState(started=True, phase="started"))
    assert len(tokeniser._allowed_token_cache) == 1


def test_midi_public_report_and_iterable_validation_branches():
    for arguments in (
        ("code", "invalid", 0, 0, 0, ""),
        ("code", "warning", -1, 0, 0, ""),
        ("code", "warning", 0, 0, 0, 1),
    ):
        with pytest.raises(MidiError):
            MidiDiagnostic(*arguments)  # type: ignore[arg-type]
    with pytest.raises(MidiError):
        MidiImportReport(0, 24, 1, 0)
    with pytest.raises(MidiError):
        MidiLoadResult((), object())  # type: ignore[arg-type]

    midi_file = _midi_with_messages(mido.MetaMessage("end_of_track", time=0))
    with pytest.raises(MidiError):
        load_midi(midi_file, track_groups=1)  # type: ignore[arg-type]
    with pytest.raises(MidiError):
        load_midi(midi_file, meta_track_indices=([0],))  # type: ignore[arg-type]
    midi_file.ticks_per_beat = True
    with pytest.raises(MidiError):
        load_midi(midi_file)
    midi_file.ticks_per_beat = 24
    midi_file.type = 3
    with pytest.raises(MidiError):
        load_midi(midi_file)
    with pytest.raises(MidiError):
        to_mido((object(),))  # type: ignore[arg-type]
    with pytest.raises(MidiError):
        to_mido((Sequence(ticks_per_quarter=32768),))
    with pytest.raises(MidiError):
        to_mido((Sequence(),), track_names=("not MIDI text: " + chr(0x1F600),))


def test_incremental_grammar_relative_and_time_signature_branches():
    tokeniser = NotelikeTokeniser(NotelikeConfig(include_time_signatures=True, pitch_range=(60, 60), note_values=(3,)))
    started = tokeniser.advance(tokeniser.initial_state(), tokeniser.start_token_id)
    meter = tokeniser.advance(started, tokeniser.token_to_id["tsg_03_04"])
    assert meter.bar_capacity == 72
    completed = tokeniser.advance(meter, tokeniser.token_to_id["bar"])
    assert completed.bar_count == 1 and completed.bar_position == 0
    for invalid_token in ("pad", "sta", "pos_000", "pos_bad", "tsg_bad_04", "tsg_03_00", "trk_99"):
        assert tokeniser._advance_token(started, invalid_token) is None
    assert tokeniser._advance_token(started, "") is None
    assert tokeniser._advance_token(started, "rst_01") is None
    assert tokeniser._advance_token(started, "unknown") is None

    assert tokeniser._advance_token(started, "rst_03") is None
    assert tokeniser._advance_token(started, "rst_000") is None
    assert tokeniser._advance_token(started, "rst_bad") is None


def test_tokeniser_preserves_meter_changes_and_exact_duration():
    tokeniser = NotelikeTokeniser(NotelikeConfig(include_time_signatures=True, pitch_range=(60, 64), note_values=(12,)))
    source = Sequence(
        (Note(72, 84, 64, 80),),
        (TimeSignature(0, 3, 4), TimeSignature(72, 2, 4)),
        110,
        24,
    )
    tokens = tokeniser.tokenise((source,))
    assert "tsg_03_04" in tokens and "tsg_02_04" in tokens
    restored = tokeniser.detokenise(tokens)[0]
    assert restored.duration_ticks == 110
    assert restored.notes[0].start == 72
    assert restored.events == source.events

    with pytest.raises(TokenisationError):
        tokeniser.tokenise((Sequence((Note(0, 12, 59, 80),), (), 12, 24),))
    with pytest.raises(TokenisationError):
        tokeniser.tokenise((Sequence((), (TimeSignature(0, 17, 16),), 102, 24),))


def test_factory_reconstructs_persisted_configuration():
    tokeniser = create_tokeniser(
        "notelike",
        {"num_tracks": 2, "pitch_range": [60, 72], "note_values": [6, 12], "velocity_bins": 4},
    )
    assert tokeniser.codec_id == "notelike"
    assert tokeniser.config == NotelikeConfig(
        num_tracks=2,
        pitch_range=(60, 72),
        note_values=(6, 12),
        velocity_bins=4,
    )
    assert create_tokeniser("notelike").config == NotelikeConfig()
    with pytest.raises(TokenisationError):
        create_tokeniser("missing")
    with pytest.raises(TokenisationError):
        create_tokeniser("notelike", {"unknown_parameter": True})


def _midi_with_messages(*messages, ticks_per_quarter=24):
    midi_file = mido.MidiFile(ticks_per_beat=ticks_per_quarter)
    midi_file.tracks.append(mido.MidiTrack(messages))
    return midi_file


def test_midi_grouping_scaling_events_diagnostics_and_file_io(tmp_path: Path):
    midi_file = mido.MidiFile(ticks_per_beat=48)
    midi_file.tracks.append(
        mido.MidiTrack(
            [
                mido.MetaMessage("time_signature", numerator=3, denominator=4, time=0),
                mido.MetaMessage("key_signature", key="Am", time=0),
                mido.MetaMessage("set_tempo", tempo=400_000, time=0),
                mido.MetaMessage("marker", text="ignored", time=0),
                mido.MetaMessage("end_of_track", time=48),
            ]
        )
    )
    midi_file.tracks.append(
        mido.MidiTrack(
            [
                mido.Message("program_change", program=4, channel=2, time=0),
                mido.Message("control_change", control=64, value=127, channel=2, time=0),
                mido.Message("pitchwheel", pitch=100, channel=2, time=0),
                mido.Message("note_on", note=60, velocity=80, channel=2, time=0),
                mido.Message("note_off", note=60, velocity=0, channel=2, time=48),
            ]
        )
    )
    result = load_midi(
        midi_file,
        track_groups=((0, 1),),
        meta_track_indices=(0,),
        target_ticks_per_quarter=24,
    )
    assert result.report.source_ticks_per_quarter == 48
    assert result.report.target_ticks_per_quarter == 24
    assert result.report.notes_created == 1
    assert not result.report.repaired
    assert {diagnostic.code for diagnostic in result.report.warnings} == {
        "unsupported_channel_message",
        "unsupported_meta_message",
    }
    assert not result.report.errors
    sequence = result.sequences[0]
    assert sequence.notes[0].end == 24
    exported = to_mido((sequence,), track_names=("merged",))
    types = {message.type for message in exported.tracks[0]}
    assert {"time_signature", "key_signature", "set_tempo", "control_change", "program_change"} <= types
    destination = tmp_path / "roundtrip.mid"
    save_midi((sequence,), destination, track_names=(None,))
    assert load_midi(destination).sequences[0].notes


@pytest.mark.parametrize(
    "kwargs",
    [
        {"mode": "invalid"},
        {"target_ticks_per_quarter": 0},
        {"track_groups": ()},
        {"track_groups": ((),)},
        {"track_groups": ((True,),)},
        {"track_groups": ((1,),)},
        {"track_groups": ((0,), (0,))},
        {"track_groups": ((0,),), "meta_target": 1},
        {"track_groups": ((0,),), "meta_target": False},
        {"meta_track_indices": (1,)},
        {"meta_track_indices": (False,)},
        {"target_ticks_per_quarter": True},
    ],
)
def test_midi_import_argument_validation(kwargs):
    midi_file = _midi_with_messages(mido.MetaMessage("end_of_track", time=0))
    with pytest.raises(MidiError):
        load_midi(midi_file, **kwargs)


def test_midi_repair_diagnostic_branches():
    unmatched = load_midi(_midi_with_messages(mido.Message("note_off", note=60, velocity=0, time=1)))
    assert unmatched.report.repaired
    assert unmatched.report.errors[0].code == "unmatched_note_off"

    zero_length = load_midi(
        _midi_with_messages(
            mido.Message("note_on", note=60, velocity=80, time=0),
            mido.Message("note_off", note=60, velocity=0, time=0),
        )
    )
    assert zero_length.report.errors[0].code == "zero_length_note"

    unclosed = load_midi(
        _midi_with_messages(
            mido.Message("note_on", note=60, velocity=80, time=0),
            mido.MetaMessage("end_of_track", time=4),
        )
    )
    assert unclosed.report.errors[0].code == "unclosed_note"
    discarded = load_midi(_midi_with_messages(mido.Message("note_on", note=60, velocity=80, time=0)))
    assert discarded.report.errors[0].code == "zero_length_unclosed_note"

    bad_channel = SimpleNamespace(type="control_change", time=0, control="bad", value=0, channel=0, is_meta=False)
    bad_meta = SimpleNamespace(type="time_signature", time=0, numerator=4, denominator=3, is_meta=True)
    malformed = load_midi(_midi_with_messages(bad_channel, bad_meta))
    assert {item.code for item in malformed.report.errors} == {"invalid_message", "invalid_meta_message"}

    overlapping = load_midi(
        _midi_with_messages(
            mido.Message("note_on", note=60, velocity=80, time=0),
            mido.Message("note_on", note=60, velocity=90, time=1),
            mido.Message("note_off", note=60, velocity=0, time=1),
            mido.Message("note_off", note=60, velocity=0, time=1),
        )
    )
    assert "overlapping_note_on" in {item.code for item in overlapping.report.errors}
    assert [(note.start, note.end) for note in overlapping.sequences[0].notes] == [(0, 1), (1, 2)]
    assert load_midi(to_mido(overlapping.sequences), mode="strict").sequences == overlapping.sequences

    invalid_delta = load_midi(_midi_with_messages(mido.MetaMessage("end_of_track", time=-1)))
    assert invalid_delta.report.errors[0].code == "invalid_delta_time"

    invalid_velocity = _midi_with_messages(
        SimpleNamespace(type="note_on", note=60, velocity=-1, channel=0, time=0, is_meta=False)
    )
    assert load_midi(invalid_velocity).report.errors[0].code == "invalid_message"
    with pytest.raises(MidiImportError):
        load_midi(_midi_with_messages(mido.MetaMessage("end_of_track", time=0.5)), mode="strict")

    grouped = mido.MidiFile(ticks_per_beat=24)
    grouped.tracks.append(
        mido.MidiTrack(
            [
                mido.Message("note_on", note=60, velocity=80, time=0),
                mido.MetaMessage("end_of_track", time=4),
            ]
        )
    )
    grouped.tracks.append(mido.MidiTrack([mido.MetaMessage("end_of_track", time=100)]))
    grouped_result = load_midi(grouped, track_groups=((0, 1),))
    assert grouped_result.sequences[0].notes[0].end == 4


def test_midi_tick_scaling_uses_exact_integer_arithmetic():
    for value, source_ppqn, target_ppqn in (
        (1, 2, 1),
        (3, 2, 1),
        (5, 2, 1),
        (7, 2, 1),
        (2**54 + 1, 960, 7),
        (2**100 + 123, 32_767, 32_766),
    ):
        assert _scaled(value, source_ppqn, target_ppqn) == round(Fraction(value * target_ppqn, source_ppqn))

    start = 2**54 + 1
    midi_file = _midi_with_messages(
        mido.Message("note_on", note=60, velocity=80, time=start),
        mido.Message("note_off", note=60, velocity=0, time=959),
        ticks_per_quarter=960,
    )

    note = load_midi(midi_file, target_ticks_per_quarter=7, mode="strict").sequences[0].notes[0]
    assert note.start == round(Fraction(start * 7, 960))
    assert note.end == round(Fraction((start + 959) * 7, 960))


def test_midi_export_validation_and_event_dispatch():
    with pytest.raises(MidiError):
        to_mido(())
    with pytest.raises(MidiError):
        to_mido((Sequence(), Sequence(ticks_per_quarter=48)))
    with pytest.raises(MidiError):
        to_mido((Sequence(),), meta_source=1)
    with pytest.raises(MidiError):
        to_mido((Sequence(),), track_names=("one", "two"))
    with pytest.raises(MidiError):
        to_mido((Sequence(),), track_names=(1,))  # type: ignore[arg-type]
    with pytest.raises(MidiError):
        _mido_event(object())  # type: ignore[arg-type]
    global_event_on_non_meta_track = Sequence((), (Tempo(0, 500_000),), 1)
    exported = to_mido((Sequence(duration_ticks=1), global_event_on_non_meta_track), meta_source=0)
    assert all(message.type != "set_tempo" for message in exported.tracks[1])

    ambiguous = Sequence(
        (Note(0, 15, 60, 80), Note(5, 10, 60, 90)),
        (),
        15,
        24,
    )
    with pytest.raises(MidiError, match="overlapping"):
        to_mido((ambiguous,))


def test_lossless_midi_mode_rejects_ignored_information():
    midi_file = _midi_with_messages(
        mido.Message("pitchwheel", pitch=100, time=0),
        mido.MetaMessage("end_of_track", time=0),
    )
    strict = load_midi(midi_file, mode="strict")
    assert strict.report.lossy and not strict.report.repaired
    with pytest.raises(MidiImportError) as error:
        load_midi(midi_file, mode="lossless")
    assert error.value.report.warnings


def test_core_defensive_validation_and_context_branches():
    class BrokenIterable:
        def __iter__(self):
            raise TypeError("broken")

    for arguments in ((1, 1, 60, 80), (0, 1, 60, 80, 0, 128)):
        with pytest.raises(ValidationError):
            Note(*arguments)
    for notes, events in (("notes", ()), ((), "events"), (BrokenIterable(), ()), ((), BrokenIterable())):
        with pytest.raises(ValidationError):
            Sequence(notes, events)  # type: ignore[arg-type]

    sequence = Sequence((Note(1, 2, 60, 80),), (), 4, 24)
    for invalid in ("steps", 1, (1, "bad")):
        with pytest.raises(ValidationError):
            sequence.quantise(invalid)  # type: ignore[arg-type]
    assert sequence.quantise((4,)).notes[0].end > sequence.quantise((4,)).notes[0].start
    with pytest.raises(ValidationError):
        Sequence().with_velocity(0)
    with pytest.raises(ValidationError):
        Sequence().filter_events(1)  # type: ignore[arg-type]
    for pitch_range in ("ab", 1, (0,), (0, 1, 2)):
        with pytest.raises(ValidationError):
            sequence.transpose(0, pitch_range=pitch_range)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        sequence.similarity(sequence, compare_velocity=1)  # type: ignore[arg-type]

    for composition in (Sequence.merge, Sequence.concatenate):
        for invalid in ("sequences", 1, (object(),)):
            with pytest.raises(ValidationError):
                composition(invalid)  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        bar_spans(object())  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        bar_spans(Sequence(), strict=1)  # type: ignore[arg-type]
    with pytest.raises(SequenceError, match="integral"):
        bar_spans(Sequence((), (TimeSignature(0, 1, 8),), 1, 1))
    assert [
        span.duration_ticks for span in bar_spans(Sequence((), (TimeSignature(1, 3, 4),), 73, 24), strict=False)
    ] == [
        1,
        72,
    ]

    for sequences, kwargs in (
        ("sequences", {}),
        (1, {}),
        ((), {"meta_track_index": False}),
        ((), {"strict": 1}),
        ((), {"carry_context": 1}),
        ((object(),), {}),
        ((Sequence(),), {"meta_track_index": 1}),
    ):
        with pytest.raises((ValidationError, SequenceError)):
            split_bars(sequences, **kwargs)  # type: ignore[arg-type]

    context = Sequence(
        (),
        (
            TimeSignature(0, 4, 4),
            KeySignature(0, Key.C),
            Tempo(0, 500_000),
            ProgramChange(0, 5, 2),
            ControlChange(0, 64, 127, 2),
        ),
        192,
        24,
    )
    second_bar = split_bars((context,))[0][1]
    assert {type(event) for event in second_bar.events} == {
        TimeSignature,
        KeySignature,
        Tempo,
        ProgramChange,
        ControlChange,
    }


def test_tokeniser_and_midi_defensive_validation_branches():
    with pytest.raises(TokenisationError):
        VocabularyManifest("codec", "{}", 1, "bad")  # type: ignore[arg-type]
    for arguments in (
        {"meter_denominator": 3},
        {"last_note_key": (1, 2)},
        {"pending_note_ticks": -1},
        {"meter_declared": 1},
    ):
        with pytest.raises(TokenisationError):
            TokeniserState(**arguments)  # type: ignore[arg-type]

    tokeniser = NotelikeTokeniser(NotelikeConfig(note_values=(24, 6, 12)))
    assert tokeniser.config.note_values == (6, 12, 24)
    for token_ids in (1, "ids", [True], [1.5], [999_999]):
        with pytest.raises(TokenisationError):
            tokeniser.decode(token_ids)  # type: ignore[arg-type]
    with pytest.raises(TokenisationError):
        tokeniser.inspect_prefix(1)  # type: ignore[arg-type]
    with pytest.raises(TokenisationError):
        tokeniser.frame(("sta",))
    with pytest.raises(TokenisationError):
        tokeniser.unframe(("sta", "sta", "sto"))
    with pytest.raises(TokenisationError):
        tokeniser.allowed_token_ids(TokeniserState(position_track_floor=1))
    with pytest.raises(TokenisationError):
        tokeniser.state_key(TokeniserState(position_track_floor=1))
    with pytest.raises(TokenisationError):
        tokeniser.tokenise_body(1)
    with pytest.raises(TokenisationError):
        tokeniser.tokenise_body((Sequence(ticks_per_quarter=48),))
    with pytest.raises(TokenisationError):
        create_tokeniser(1)  # type: ignore[arg-type]
    with pytest.raises(TokenisationError):
        create_tokeniser("notelike", 1)  # type: ignore[arg-type]

    for factory in (
        lambda: MidiImportReport(24, 24, 1, 0, "diagnostics"),
        lambda: MidiImportReport(24, 24, 1, 0, 1),
        lambda: MidiLoadResult("sequences", MidiImportReport(24, 24, 1, 0)),
        lambda: MidiLoadResult(1, MidiImportReport(24, 24, 1, 0)),
    ):
        with pytest.raises(MidiError):
            factory()  # type: ignore[misc]
    for sequences, names in (("sequences", None), (1, None), ((Sequence(),), "name"), ((Sequence(),), 1)):
        with pytest.raises(MidiError):
            to_mido(sequences, track_names=names)  # type: ignore[arg-type]
