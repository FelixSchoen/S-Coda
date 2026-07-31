import pickle
from dataclasses import FrozenInstanceError, replace

import mido
import pytest
from hypothesis import given
from hypothesis import strategies as st

from scoda import (
    ControlChange,
    Key,
    KeySignature,
    MidiError,
    MidiImportError,
    Note,
    NotelikeConfig,
    NotelikeTokeniser,
    ProgramChange,
    Sequence,
    SequenceError,
    Tempo,
    TimeSignature,
    TokenisationError,
    ValidationError,
    load_midi,
    split_bars,
    to_mido,
)


def test_values_are_frozen_and_sequences_do_not_alias_inputs():
    note = Note(0, 12, 60, 90, 2)
    source = [note]
    sequence = Sequence(source, (), 12, 24)
    source.clear()
    assert sequence.notes == (note,)
    with pytest.raises(FrozenInstanceError):
        note.pitch = 61


def test_tokeniser_pickle_reconstructs_immutable_derived_state():
    tokeniser = NotelikeTokeniser(NotelikeConfig(num_tracks=2, note_values=(6, 12, 24), velocity_bins=2))

    restored = pickle.loads(pickle.dumps(tokeniser))

    assert restored is not tokeniser
    assert restored.config == tokeniser.config
    assert restored.manifest == tokeniser.manifest
    assert restored.vocabulary == tokeniser.vocabulary
    assert restored.token_to_id == tokeniser.token_to_id


def test_sequence_note_order_is_canonical_across_release_velocities():
    notes = (
        Note(0, 12, 60, 64, release_velocity=2),
        Note(0, 12, 60, 64, release_velocity=1),
    )

    assert Sequence(notes, (), 12) == Sequence(tuple(reversed(notes)), (), 12)


def test_octave_wrap_is_constant_time_for_large_transpositions():
    sequence = Sequence((Note(0, 12, 60, 64),), (), 12)

    assert sequence.transpose(10**100, out_of_range="octave_wrap").notes[0].pitch == 124
    assert sequence.transpose(-(10**100), out_of_range="octave_wrap").notes[0].pitch == 8


@pytest.mark.parametrize(
    "arguments",
    [(-1, 1, 60, 90, 0), (0, 0, 60, 90, 0), (0, 1, 128, 90, 0), (0, 1, 60, 0, 0), (0, 1, 60, 90, 16)],
)
def test_note_validation(arguments):
    with pytest.raises(ValidationError):
        Note(*arguments)


def test_split_and_concatenate_preserve_sounding_occupancy():
    sequence = Sequence((Note(6, 18, 60, 90),), (), 24, 24)
    first, second = sequence.split((12,))
    assert first.notes == (Note(6, 12, 60, 90),)
    assert second.notes == (Note(0, 6, 60, 90),)
    assert Sequence.concatenate((first, second)).duration_ticks == 24


def test_bar_split_rejects_mid_bar_meter_change():
    sequence = Sequence(
        (),
        (TimeSignature(0, 4, 4), TimeSignature(48, 3, 4)),
        120,
        24,
    )
    with pytest.raises(Exception, match="mid-bar"):
        split_bars((sequence,))


def test_midi_repairs_and_strict_mode():
    midi = mido.MidiFile(ticks_per_beat=24)
    track = mido.MidiTrack()
    track.extend(
        [
            mido.Message("note_off", note=61, channel=0, time=0),
            mido.Message("note_on", note=60, velocity=90, channel=1, time=3),
            mido.MetaMessage("end_of_track", time=9),
        ]
    )
    midi.tracks.append(track)
    result = load_midi(midi)
    assert result.sequences[0].notes == (Note(3, 12, 60, 90, 1),)
    assert {item.code for item in result.report.errors} == {"unmatched_note_off", "unclosed_note"}
    with pytest.raises(MidiImportError) as error:
        load_midi(midi, mode="strict")
    assert error.value.report.errors


def test_midi_roundtrip_preserves_semantics_and_trailing_duration():
    sequence = Sequence(
        (Note(4, 12, 64, 100, 3),),
        (TimeSignature(0, 4, 4), KeySignature(0, Key.E_MINOR)),
        24,
        24,
    )
    result = load_midi(to_mido((sequence,)), mode="strict")
    assert result.sequences == (sequence,)


def test_lossless_midi_preserves_order_sensitive_same_tick_events():
    event_sequences = (
        (ProgramChange(0, 5, 2), ProgramChange(0, 10, 2)),
        (ControlChange(0, 0, 1, 2), ProgramChange(0, 10, 2)),
        (
            ControlChange(0, 101, 0, 2),
            ControlChange(0, 100, 0, 2),
            ControlChange(0, 6, 12, 2),
        ),
    )

    for events in event_sequences:
        sequence = Sequence((), events, 0, 24)
        assert sequence.events == events
        assert load_midi(to_mido((sequence,)), mode="lossless").sequences == (sequence,)


def test_midi_import_reports_same_tick_channel_state_reordering():
    midi_file = mido.MidiFile(ticks_per_beat=24)
    midi_file.tracks.append(
        mido.MidiTrack(
            [
                mido.Message("note_on", note=60, velocity=80, channel=2, time=0),
                mido.Message("program_change", program=10, channel=2, time=0),
                mido.Message("note_off", note=60, velocity=0, channel=2, time=12),
            ]
        )
    )

    repaired = load_midi(midi_file)
    assert "reordered_same_tick_channel_state" in {item.code for item in repaired.report.errors}
    with pytest.raises(MidiImportError):
        load_midi(midi_file, mode="strict")
    assert load_midi(to_mido(repaired.sequences), mode="lossless").sequences == repaired.sequences


def test_incremental_state_matches_prefix_inspection():
    tokeniser = NotelikeTokeniser(NotelikeConfig(num_tracks=2))
    tokens = ["sta", "trk_01", "pit_060-val_12-vel_064", "bar", "sto"]
    ids = tokeniser.encode(tokens)
    state = tokeniser.initial_state()
    for token_id in ids:
        assert token_id in tokeniser.allowed_token_ids(state)
        state = tokeniser.advance(state, token_id)
    assert state == tokeniser.inspect_prefix(ids)
    assert state.ended and state.bar_count == 1


def test_meterless_tokenisation_keeps_implicit_four_quarter_bars():
    tokeniser = NotelikeTokeniser(NotelikeConfig(max_bar_quarters=8, note_values=(12,)))
    sequence = Sequence((Note(120, 132, 60, 64),), (), 192, 24)

    tokens = tokeniser.tokenise((sequence,))

    assert tokens.count("bar") == 2
    assert tokeniser.tokenise(tokeniser.detokenise(tokens)) == tokens


def test_dissertation_codec_has_compact_end_of_bar_vocabulary():
    tokeniser = NotelikeTokeniser(
        NotelikeConfig(
            num_tracks=6,
            note_values=(4, 6, 8, 9, 12, 16, 18, 24, 36),
        )
    )

    assert tokeniser.vocabulary_size == 897
    assert "pos_095" in tokeniser.token_to_id
    assert "pos_096" not in tokeniser.token_to_id

    complete = Sequence((Note(0, 24, 60, 64),), (), 96, 24)
    empty = Sequence((), (), 96, 24)
    tokens = tokeniser.tokenise((complete, empty, empty, empty, empty, empty))
    assert tokens == ["sta", "trk_00", "pit_060-val_24-vel_064", "bar", "sto"]
    metadata = tokeniser.metadata(tokens)
    boundary = tokens.index("bar")
    assert metadata.tick[boundary] == 96
    assert metadata.tick_in_bar[boundary] == 96


def test_partial_final_bar_uses_exact_position_without_bar_boundary():
    tokeniser = NotelikeTokeniser(NotelikeConfig(pitch_range=(60, 60), note_values=(12,)))
    sequence = Sequence((Note(0, 12, 60, 64),), (), 72, 24)

    tokens = tokeniser.tokenise((sequence,))

    assert tokens == ["sta", "trk_00", "pit_060-val_12-vel_064", "pos_072", "sto"]
    assert tokeniser.detokenise(tokens) == (sequence,)


def test_running_track_context_is_preserved_across_bar_boundaries():
    tokeniser = NotelikeTokeniser(NotelikeConfig(pitch_range=(60, 60), note_values=(12,)))
    sequence = Sequence(
        (
            Note(0, 12, 60, 64),
            Note(96, 108, 60, 64),
        ),
        (),
        192,
        24,
    )

    tokens = tokeniser.tokenise((sequence,))

    assert tokens == [
        "sta",
        "trk_00",
        "pit_060-val_12-vel_064",
        "bar",
        "pit_060-val_12-vel_064",
        "bar",
        "sto",
    ]
    assert tokeniser.detokenise(tokens) == (sequence,)


def test_codec_roundtrip_handles_simultaneous_tracks():
    tokeniser = NotelikeTokeniser(NotelikeConfig(num_tracks=2))
    sequences = (
        Sequence((Note(12, 24, 60, 64, 0),), (), 96, 24),
        Sequence((Note(12, 24, 64, 64, 1),), (), 96, 24),
    )
    tokens = tokeniser.tokenise(sequences)
    assert tokens.count("pos_012") == 1
    decoded = tokeniser.detokenise(tokens)
    assert decoded[0].notes[0].pitch == 60
    assert decoded[1].notes[0].pitch == 64


@given(
    start=st.integers(min_value=0, max_value=500),
    duration=st.integers(min_value=1, max_value=200),
    pitch=st.integers(min_value=0, max_value=127),
    velocity=st.integers(min_value=1, max_value=127),
    channel=st.integers(min_value=0, max_value=15),
)
def test_property_midi_roundtrip_for_single_notes(start, duration, pitch, velocity, channel):
    note = Note(start, start + duration, pitch, velocity, channel)
    sequence = Sequence((note,), (), note.end + 11, 24)
    assert load_midi(to_mido((sequence,)), mode="strict").sequences == (sequence,)


@given(st.lists(st.sampled_from(["bar", "trk_00", "pit_060-val_12-vel_064"]), max_size=20))
def test_property_incremental_state_matches_valid_full_prefix(body):
    tokeniser = NotelikeTokeniser(NotelikeConfig())
    tokens = ["sta"]
    state = tokeniser.advance(tokeniser.initial_state(), tokeniser.start_token_id)
    for token in body:
        token_id = tokeniser.token_to_id[token]
        if token_id in tokeniser.allowed_token_ids(state):
            tokens.append(token)
            state = tokeniser.advance(state, token_id)
    assert tokeniser.inspect_prefix(tokeniser.encode(tokens)) == state


def test_quantised_note_tail_defines_the_canonical_endpoint():
    tokeniser = NotelikeTokeniser(NotelikeConfig(note_values=(3,)))
    sequence = Sequence((Note(64, 65, 60, 64),), (), 65, 24)

    tokens = tokeniser.tokenise((sequence,))

    assert tokens[-2] == "pos_067"
    decoded = tokeniser.detokenise(tokens)
    assert decoded[0].duration_ticks == 67
    assert tokeniser.tokenise(decoded) == tokens


@given(
    tracks=st.tuples(
        st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=180),
                st.integers(min_value=1, max_value=80),
                st.integers(min_value=48, max_value=72),
                st.integers(min_value=1, max_value=127),
            ),
            max_size=12,
        ),
        st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=180),
                st.integers(min_value=1, max_value=80),
                st.integers(min_value=48, max_value=72),
                st.integers(min_value=1, max_value=127),
            ),
            max_size=12,
        ),
    ),
    trailing=st.integers(min_value=0, max_value=30),
)
def test_property_token_streams_are_stable_canonical_roundtrips(tracks, trailing):
    tokeniser = NotelikeTokeniser(
        NotelikeConfig(num_tracks=2, pitch_range=(48, 72), note_values=(3, 6, 12, 24, 48), velocity_bins=8)
    )
    sequences = []
    for track, raw_notes in enumerate(tracks):
        notes = tuple(
            Note(start, start + duration, pitch, velocity, track) for start, duration, pitch, velocity in raw_notes
        )
        duration = max((note.end for note in notes), default=0) + trailing
        sequences.append(Sequence(notes, (), duration, 24))

    tokens = tokeniser.tokenise(tuple(sequences))

    assert tokeniser.tokenise(tokeniser.detokenise(tokens)) == tokens


@pytest.mark.parametrize(
    "tokens",
    [
        (),
        ("sta",),
        ("sta", "bar"),
        ("sta", "trk_00", "pit_060-val_12-vel_064", "sto"),
        ("sta", "trk_00", "trk_00", "pit_060-val_12-vel_064", "bar", "sto"),
        (
            "sta",
            "trk_01",
            "pit_060-val_12-vel_064",
            "trk_00",
            "pit_061-val_12-vel_064",
            "bar",
            "sto",
        ),
        (
            "sta",
            "trk_00",
            "pit_061-val_12-vel_064",
            "pit_060-val_12-vel_064",
            "bar",
            "sto",
        ),
    ],
)
def test_decoder_rejects_incomplete_and_noncanonical_streams(tokens):
    tokeniser = NotelikeTokeniser(NotelikeConfig(num_tracks=2))
    with pytest.raises(TokenisationError):
        tokeniser.detokenise(tokens)


@pytest.mark.parametrize(
    "tokens",
    [
        ("sta", "bar", "sto"),
        ("sta", "tsg_04_04", "bar", "tsg_04_04", "bar", "sto"),
    ],
)
def test_time_signature_grammar_requires_canonical_running_meter(tokens):
    tokeniser = NotelikeTokeniser(NotelikeConfig(include_time_signatures=True))
    with pytest.raises(TokenisationError):
        tokeniser.detokenise(tokens)


def test_supports_all_positive_midi_velocity_bins_without_collisions():
    tokeniser = NotelikeTokeniser(NotelikeConfig(pitch_range=(60, 60), note_values=(12,), velocity_bins=127))
    velocities = {token.rsplit("_", 1)[1] for token in tokeniser.manifest.tokens if token.startswith("pit_")}
    assert len(velocities) == 127


def test_preclassified_constraint_candidates_match_exhaustive_masks():
    tokeniser = NotelikeTokeniser(
        NotelikeConfig(
            num_tracks=2, pitch_range=(60, 64), note_values=(6, 12), velocity_bins=4, include_time_signatures=True
        )
    )
    sequences = (
        Sequence(
            (Note(0, 12, 60, 40), Note(96, 102, 64, 100)),
            (TimeSignature(0, 4, 4), TimeSignature(96, 3, 4)),
            168,
            24,
        ),
        Sequence((Note(0, 6, 62, 80, 1),), (), 168, 24),
    )
    state = tokeniser.initial_state()
    for token in tokeniser.tokenise(sequences):
        exhaustive = frozenset(
            token_id
            for token_id, candidate in enumerate(tokeniser.vocabulary)
            if tokeniser._advance_token(state, candidate) is not None
        )
        assert tokeniser.allowed_token_ids(state) == exhaustive
        state = tokeniser.advance(state, tokeniser.token_to_id[token])


def test_sequence_boundaries_and_ppqn_comparisons_are_explicit():
    terminal = Tempo(96, 500_000)
    sequence = Sequence((Note(0, 24, 60, 80, 0, 73),), (terminal,), 96, 24)

    assert sequence.slice(0, sequence.duration_ticks) == sequence
    assert sequence.slice(5, 5) == Sequence(ticks_per_quarter=24)
    assert sequence.split((48,))[-1].events == (Tempo(48, 500_000),)

    same_duration = Sequence((Note(0, 48, 60, 80),), (), 192, 48)
    assert sequence.duration_relation(same_duration) == 1.0
    with pytest.raises(SequenceError, match="PPQN"):
        sequence.similarity(same_duration)
    assert sequence.resample(48).similarity(same_duration) < 1.0

    with pytest.raises(SequenceError, match="PPQN"):
        split_bars((sequence, same_duration))


def test_bar_context_cache_preserves_full_time_signature_values():
    sequence = Sequence(
        (),
        (TimeSignature(0, 4, 4, 24, 8), TimeSignature(96, 4, 4, 36, 16)),
        192,
        24,
    )

    bars = split_bars((sequence,))[0]

    assert bars[0].events[0] == TimeSignature(0, 4, 4, 24, 8)
    assert bars[1].events[0] == TimeSignature(0, 4, 4, 36, 16)


def test_bar_context_preserves_ordered_channel_state_history():
    bank_events = (
        ControlChange(0, 0, 1, 2),
        ControlChange(0, 32, 2, 2),
        ProgramChange(0, 10, 2),
    )
    bank_sequence = Sequence((), bank_events, 192, 24)

    bank_bars = split_bars((bank_sequence,))[0]
    assert tuple(event for event in bank_bars[0].events if not isinstance(event, TimeSignature)) == bank_events
    assert tuple(event for event in bank_bars[1].events if not isinstance(event, TimeSignature)) == bank_events
    assert split_bars((bank_sequence,), carry_context=False)[0][0].events == bank_events
    assert split_bars((bank_sequence,), carry_context=False)[0][1].events == ()

    controller_history = (
        ControlChange(0, 6, 12, 2),
        ControlChange(12, 101, 0, 2),
        ControlChange(12, 100, 0, 2),
        ControlChange(12, 6, 24, 2),
    )
    controller_sequence = Sequence((), controller_history, 192, 24)

    second_bar = split_bars((controller_sequence,))[0][1]
    carried = tuple(event for event in second_bar.events if not isinstance(event, TimeSignature))
    assert carried == tuple(replace(event, time=0) for event in controller_history)


def test_lossless_midi_preserves_release_velocity_and_full_time_signature():
    midi_file = mido.MidiFile(ticks_per_beat=24)
    midi_file.tracks.append(
        mido.MidiTrack(
            [
                mido.MetaMessage(
                    "time_signature",
                    numerator=3,
                    denominator=4,
                    clocks_per_click=36,
                    notated_32nd_notes_per_beat=16,
                    time=0,
                ),
                mido.Message("note_on", note=60, velocity=90, time=0),
                mido.Message("note_off", note=60, velocity=73, time=12),
                mido.MetaMessage("end_of_track", time=12),
            ]
        )
    )

    loaded = load_midi(midi_file, mode="lossless")

    assert loaded.report.diagnostics == ()
    assert loaded.sequences[0].notes[0].release_velocity == 73
    assert loaded.sequences[0].events[0] == TimeSignature(0, 3, 4, 36, 16)
    assert load_midi(to_mido(loaded.sequences), mode="lossless").sequences == loaded.sequences


def test_midi_format_two_and_lossy_ppqn_resampling_are_never_silent():
    format_two = mido.MidiFile(type=2, ticks_per_beat=24)
    format_two.tracks.append(mido.MidiTrack([mido.MetaMessage("end_of_track", time=0)]))
    with pytest.raises(MidiError, match="format 2"):
        load_midi(format_two)

    midi_file = mido.MidiFile(ticks_per_beat=24)
    midi_file.tracks.append(
        mido.MidiTrack(
            [
                mido.Message("note_on", note=60, velocity=90, time=1),
                mido.Message("note_off", note=60, velocity=0, time=5),
                mido.MetaMessage("end_of_track", time=0),
            ]
        )
    )
    strict = load_midi(midi_file, target_ticks_per_quarter=10, mode="strict")
    assert "quantized_tick" in {diagnostic.code for diagnostic in strict.report.warnings}
    with pytest.raises(MidiImportError) as error:
        load_midi(midi_file, target_ticks_per_quarter=10, mode="lossless")
    assert "quantized_tick" in {diagnostic.code for diagnostic in error.value.report.warnings}
