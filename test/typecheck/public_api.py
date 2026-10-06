"""Strict type-checking smoke test for an external S-Coda consumer."""

from typing import assert_type

from scoda import (
    BarSpan,
    Key,
    KeySignature,
    MidiLoadResult,
    Note,
    NoteDurationPolicy,
    NotelikeConfig,
    NotelikeTokeniser,
    Sequence,
    SequenceBuilder,
    TimeSignature,
    TokeniserState,
    TokenMetadata,
    VocabularyManifest,
    bar_spans,
    create_tokeniser,
    load_midi,
    split_bars,
)

signature = KeySignature(0, "C")
assert_type(signature.key, Key)
assert_type(Key.C.transpose(2), Key)

sequence = Sequence(
    notes=(Note(0, 24, 60, 90),),
    events=(signature,),
    duration_ticks=24,
    ticks_per_quarter=24,
)
assert_type(sequence.transpose(2), Sequence)
assert_type(sequence.slice(0, 24), Sequence)
assert_type(sequence.quantise_note_lengths((24, 96), duration_extension_ticks=96), Sequence)
duration_policy = NoteDurationPolicy((24, 96), duration_extension_ticks=96)
assert_type(duration_policy.nearest(120), int)
assert_type(duration_policy.floor(120), int | None)
assert_type(duration_policy.decompose(120), tuple[int, int])
assert_type(sequence.split((12,)), tuple[Sequence, ...])
assert_type(SequenceBuilder(24).add_note(Note(0, 12, 60, 90)).build(), Sequence)
assert_type(bar_spans(sequence), tuple[BarSpan, ...])
assert_type(split_bars((sequence,)), tuple[tuple[Sequence, ...], ...])
assert_type(load_midi("example.mid"), MidiLoadResult)

time_signature = TimeSignature(0, 4, 4, 24, 8)
assert_type(time_signature.clocks_per_click, int)
assert_type(sequence.notes[0].release_velocity, int)

tokeniser = NotelikeTokeniser(NotelikeConfig(note_values=(6, 12, 24)))
assert_type(tokeniser.tokenise((sequence,)), list[str])
assert_type(tokeniser.tokenise_body((sequence,)), list[str])
assert_type(tokeniser.initial_state(), TokeniserState)
assert_type(tokeniser.next_completion_token_id(tokeniser.initial_state()), int | None)
assert_type(tokeniser.completion_token_ids(tokeniser.initial_state(), max_tokens=16), tuple[int, ...])
assert_type(tokeniser.metadata(tokeniser.tokenise((sequence,))), TokenMetadata)
assert_type(tokeniser.prefix_metadata(["sta"]), TokenMetadata)
assert_type(tokeniser.vocabulary, tuple[str, ...])
assert_type(tokeniser.token_to_id["sta"], int)
assert_type(tokeniser.manifest, VocabularyManifest)
assert_type(create_tokeniser("notelike"), NotelikeTokeniser)
