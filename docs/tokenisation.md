# Tokenisation

`NotelikeTokeniser` maps synchronised sequences to one canonical token stream. Its immutable `NotelikeConfig` controls
the PPQN, number of tracks, pitch range, allowed note values, velocity bins, meter vocabulary, and maximum bar length.

```python
--8<-- "examples/tokenisation.py"
```

## Representation policy

The codec is deliberately lossy. Note durations and velocities are mapped to the nearest configured values, with ties
resolved towards the lower value. Track position is encoded instead of the original MIDI channel; detokenisation uses
`track_index % 16` as the note channel and release velocity `0`.

At the default resolution of 24 ticks per quarter, the default duration vocabulary contains the common straight,
triplet, and dotted values between a sixteenth-note triplet and a whole note:

```text
4, 6, 8, 9, 12, 16, 18, 24, 32, 36, 48, 64, 72, 96
```

This library default is intended as a general-purpose starting point. Machine-learning corpora should explicitly pin
the smallest musically justified `note_values` set so preprocessing and vocabulary construction remain reproducible.

`velocity_bins` divides the positive MIDI range `1..127` into equal-width categories and names each category by its
centre value. Consequently, the default single category is `vel_064`: it means "the only velocity category", not that
the input note necessarily had velocity 64. Detokenisation reconstructs that representative value, so a corpus that
normalises every input note to velocity 127 retains one stable model category but exports velocity 64. Use all 127 bins
or preserve velocity separately when exact reconstructed loudness matters.

## Bar boundaries

`bar` is an end-of-bar boundary token. A complete 4/4 bar at 24 ticks per quarter ends in `bar`; it does not also emit
the redundant `pos_096`. The boundary both closes the current bar and precedes the next bar's content. A partial final
bar instead ends with its exact position followed by `sto`, so complete and incomplete endings remain distinguishable.
The running track remains active across the boundary, avoiding a redundant track token when the next note stays on the
same track; position and note-order state reset for the new bar.

```text
complete bars:    sta ... bar ... bar sto
partial last bar: sta ... bar ... pos_048 sto
```

Position tokens range from `1` through one tick before the configured maximum bar capacity. With a larger configured
meter capacity, a position such as `pos_096` may still be a legitimate position inside that longer bar; it is never
used as the endpoint of a complete 4/4 bar.

When `include_time_signatures=True`, numerator and denominator changes from the first sequence are encoded. Their
auxiliary MIDI payload and all key, tempo, program, and controller events are not represented. Preserve that information
alongside tokens when an experiment needs it. `detokenise(tokenise(sequences))` therefore returns the codec-normalised
representation, not necessarily the original sequences.

## Framing

`tokenise()` returns a complete `sta ... sto` stream. `tokenise_body()` returns the unframed body used by pipelines that
store boundary tokens separately. `frame()` and `unframe()` convert between the forms and reject nested or missing
boundaries.

## Vocabulary

`vocabulary` is an immutable tuple whose index is the token ID. `token_to_id` is the inverse read-only mapping, and
`vocabulary_size` is their shared size. `encode()` and `decode()` validate every value and reject unknown tokens or IDs.

The manifest records the codec ID, normalised configuration JSON, ordered vocabulary, size, and SHA-256 fingerprint.
Changing any vocabulary-shaping configuration changes the fingerprint.

Configurations whose vocabulary could exceed 250,000 entries are rejected before allocation. Incremental grammar
masks use a bounded cache sized according to the vocabulary, so long-running generation services cannot retain an
unbounded number of large masks. Configured note values are also bounded by the standard MIDI variable-length tick
limit of 268,435,455, preventing pathological token text while remaining far above ordinary musical durations.

## Metadata

`metadata()` returns immutable `TokenMetadata` aligned with a complete stream; `body_metadata()` aligns with an unframed
body. It includes token indices, absolute and within-bar ticks, active track indices, pitch, and circle-of-fifths
positions. Tokens without pitch-derived values use `NaN` unless `impute_pitch=True` requests carry-forward values;
before the first note, imputation uses the neutral reference pitch A4 (`69`).

## Constrained generation

Start with `initial_state()`. For each generated token, obtain `allowed_token_ids(state)` and update the state with
`advance(state, token_id)`. `inspect_prefix()` validates and reconstructs state from an existing ID prefix. These methods
share the same grammar used by detokenisation, so model constraints cannot drift from the decoder.
