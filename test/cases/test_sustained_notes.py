"""Compositional durations must preserve attacks, causality and grammar."""

import math
import pickle
from dataclasses import replace

import mido
import pytest
from hypothesis import given
from hypothesis import strategies as st

from scoda import (
    MidiImportError,
    Note,
    NoteDurationPolicy,
    NotelikeConfig,
    NotelikeTokeniser,
    Sequence,
    TimeSignature,
    TokenisationError,
    ValidationError,
    create_tokeniser,
    load_midi,
    to_mido,
)
from scoda.duration import MAX_NOTE_DURATION_TICKS

VALUES = (4, 6, 8, 12, 16, 18, 24, 32, 36, 48, 72, 96)


def codec(**kwargs):
    return NotelikeTokeniser(NotelikeConfig(note_values=VALUES, duration_extension_ticks=96, **kwargs))


@given(st.integers(min_value=1, max_value=2000))
def test_composite_duration_policy_matches_explicit_lattice(duration):
    policy = NoteDurationPolicy(VALUES, 96)
    lattice = [count * 96 + value for count in range(23) for value in VALUES]
    expected = min(lattice, key=lambda value: (abs(value - duration), value))
    assert policy.nearest(duration) == expected
    assert policy.floor(duration) == max((value for value in lattice if value <= duration), default=None)
    count, base = policy.decompose(expected)
    assert count * 96 + base == expected


@pytest.mark.parametrize("unit", [0, -1, True, 48, "96", 96.0])
def test_invalid_duration_extension_configuration(unit):
    with pytest.raises(ValidationError):
        NoteDurationPolicy(VALUES, unit)
    with pytest.raises(TokenisationError):
        NotelikeConfig(note_values=VALUES, duration_extension_ticks=unit)


def test_duration_policy_bounds_and_finite_mode():
    assert NoteDurationPolicy(VALUES).nearest(192) == 96
    policy = NoteDurationPolicy(VALUES, 96)
    assert policy.decompose(192) == (1, 96)
    assert policy.decompose(300) == (3, 12)
    assert policy.nearest(MAX_NOTE_DURATION_TICKS) <= MAX_NOTE_DURATION_TICKS
    for invalid in (0, -1, True, MAX_NOTE_DURATION_TICKS + 1):
        with pytest.raises(ValidationError):
            policy.nearest(invalid)
    with pytest.raises(ValidationError):
        policy.decompose(97)


@pytest.mark.parametrize("onset", [0, 60, 84, 96])
@pytest.mark.parametrize("duration", [24, 96, 120, 168, 192, 300, 384])
def test_roundtrip_retains_one_attack_across_any_number_of_bars(onset, duration):
    tokeniser = codec()
    sequence = Sequence((Note(onset, onset + duration, 60, 64),), duration_ticks=onset + duration)
    tokens = tokeniser.tokenise((sequence,))
    assert tokeniser.detokenise(tokens) == (sequence,)
    assert sum(token.startswith("pit_") for token in tokens) == 1
    assert tokens.count("ext_096") == (duration - 1) // 96
    assert load_midi(to_mido((sequence,)), mode="strict").sequences == (sequence,)
    assert sequence.quantise_note_lengths(VALUES, duration_extension_ticks=96) == sequence
    state = tokeniser.initial_state()
    for token_id in tokeniser.encode(tokens):
        assert token_id in tokeniser.allowed_token_ids(state)
        state = tokeniser.advance(state, token_id)
    assert state.ended and not state.duration_extension_ticks


def test_meter_and_ppqn_do_not_change_extension_meaning():
    tokeniser = codec(include_time_signatures=True)
    sequence = Sequence((Note(60, 252, 60, 64),), (TimeSignature(0, 3, 4), TimeSignature(72, 4, 4)), 264)
    assert tokeniser.detokenise(tokeniser.tokenise((sequence,))) == (sequence,)
    scaled = sequence.resample(48)
    scaled_codec = NotelikeTokeniser(
        NotelikeConfig(
            ticks_per_quarter=48,
            note_values=tuple(value * 2 for value in VALUES),
            duration_extension_ticks=192,
            include_time_signatures=True,
        )
    )
    assert scaled_codec.detokenise(scaled_codec.tokenise((scaled,))) == (scaled,)


def test_extension_ordering_polyphony_tracks_and_manifest():
    tokeniser = codec(num_tracks=2)
    sequences = (
        Sequence((Note(0, 192, 60, 64), Note(0, 24, 61, 64)), duration_ticks=192),
        Sequence((Note(0, 120, 60, 64, channel=1),), duration_ticks=192),
    )
    tokens = tokeniser.tokenise(sequences)
    assert tokeniser.detokenise(tokens) == sequences
    assert create_tokeniser("notelike", tokeniser.manifest.normalised_config).manifest == tokeniser.manifest
    assert pickle.loads(pickle.dumps(tokeniser)).manifest == tokeniser.manifest
    assert codec(num_tracks=6).vocabulary_size == 1162
    ordinary = NotelikeTokeniser(NotelikeConfig(note_values=VALUES))
    assert "duration_extension_ticks" not in ordinary.manifest.normalised_config
    assert "ext_096" not in ordinary.vocabulary


def test_ordered_same_pitch_notes_can_require_multiple_markers_before_any_note_is_legal():
    tokeniser = codec(pitch_range=(60, 60))
    sequence = Sequence((Note(0, 288, 60, 64), Note(0, 384, 60, 64)), duration_ticks=384)
    tokens = tokeniser.tokenise((sequence,))
    assert tokeniser.detokenise(tokens) == (sequence,)
    state = tokeniser.inspect_prefix(
        tokeniser.encode(
            [
                "sta",
                "trk_00",
                "ext_096",
                "ext_096",
                "pit_060-val_96-vel_064",
                "ext_096",
            ]
        )
    )
    assert tokeniser.allowed_token_ids(state) == frozenset({tokeniser.token_to_id["ext_096"]})


@pytest.mark.parametrize("invalid", ["bar", "sto", "trk_01", "pos_024"])
def test_extension_prefix_cannot_be_abandoned(invalid):
    tokeniser = codec(num_tracks=2)
    state = tokeniser.inspect_prefix(tokeniser.encode(["sta", "trk_00", "ext_096"]))
    assert state.duration_extension_ticks == 96 and state.pending_note_ticks == 0
    with pytest.raises(TokenisationError):
        tokeniser.advance(state, tokeniser.token_to_id[invalid])
    assert tokeniser.allowed_token_ids(state) == frozenset(
        index for token, index in tokeniser.token_to_id.items() if token.startswith(("ext_", "pit_"))
    )
    with pytest.raises(TokenisationError):
        tokeniser.completion_token_ids(state)


def test_extension_metadata_does_not_look_ahead_to_pitch():
    tokeniser = codec()
    tokens = ["sta", "trk_00", "ext_096", "pit_060-val_24-vel_064", "bar", "pos_024", "sto"]
    metadata = tokeniser.metadata(tokens)
    assert metadata.tick[2:4] == (0, 0)
    assert metadata.track_index[2:4] == (0, 0)
    assert math.isnan(metadata.pitch[2]) and metadata.pitch[3] == 60
    imputed = tokeniser.metadata(tokens, impute_pitch=True)
    assert imputed.pitch[2] == 69  # Previous/default pitch, never the following note.
    for stop in range(1, len(tokens) + 1):
        prefix = tokeniser.prefix_metadata(tokens[:stop], impute_pitch=True)
        assert prefix.pitch == imputed.pitch[:stop]
        assert prefix.tick == imputed.tick[:stop]


def test_completion_suffix_is_exact_and_no_note_is_rearticulated():
    tokeniser = codec()
    sequence = Sequence((Note(84, 276, 60, 64),), duration_ticks=276)
    tokens = tokeniser.tokenise((sequence,))
    split = tokens.index("bar") + 1
    state = tokeniser.inspect_prefix(tokeniser.encode(tokens[:split]))
    assert tokeniser.decode(tokeniser.completion_token_ids(state)) == ["bar", "pos_084", "sto"]
    assert tokeniser.detokenise([*tokens[:split], *tokeniser.decode(tokeniser.completion_token_ids(state))]) == (
        sequence,
    )
    invalid_state = replace(state, duration_extension_ticks=1, phase="extension")
    with pytest.raises(TokenisationError):
        tokeniser.allowed_token_ids(invalid_state)
    assert len(tokeniser.completion_token_ids(state, max_tokens=3)) == 3
    with pytest.raises(TokenisationError, match="exceeds max_tokens"):
        tokeniser.completion_token_ids(state, max_tokens=2)
    for invalid in (-1, True, 1.5):
        with pytest.raises(TokenisationError, match="max_tokens"):
            tokeniser.completion_token_ids(state, max_tokens=invalid)


@pytest.mark.parametrize("mode", ["repair", "strict", "lossless"])
def test_drop_unclosed_note_does_not_bypass_strict_diagnostics(mode):
    midi = mido.MidiFile(ticks_per_beat=24)
    midi.tracks.append(
        mido.MidiTrack(
            [
                mido.Message("note_on", note=60, velocity=64, time=0),
                mido.Message("note_on", note=61, velocity=64, time=24),
                mido.Message("note_off", note=61, velocity=0, time=24),
                mido.MetaMessage("end_of_track", time=912),
            ]
        )
    )
    if mode != "repair":
        with pytest.raises(MidiImportError) as error:
            load_midi(midi, mode=mode, unclosed_note_policy="drop")
        assert error.value.report.errors[0].code == "unclosed_note"
    else:
        result = load_midi(midi, mode=mode, unclosed_note_policy="drop")
        assert result.sequences[0].notes == (Note(24, 48, 61, 64),)
        assert result.report.notes_created == 1
        assert result.report.errors[0].code == "unclosed_note"
