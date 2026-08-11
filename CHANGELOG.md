# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres
to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- Quantise empty sequences without raising when no notes or events contribute to their duration

## [3.0.0] - 2026-07-31

### Added

- Add immutable note, event, sequence, MIDI-import-report, tokeniser-state, and token-metadata APIs
- Add one canonical notelike codec with validated immutable configuration
- Add deterministic vocabulary manifests and SHA-256 vocabulary fingerprints
- Add incremental tokeniser state inspection for efficient constrained decoding
- Add explicit token body framing through `tokenise_body()`, `frame()`, and `unframe()`
- Add deterministic MIDI repair diagnostics plus strict and fully lossless import modes
- Make the notelike grammar canonical at bar boundaries: `bar` closes a complete bar, running track context carries
  across the boundary, partial final bars close at an explicit terminal position, and endpoint notes are rejected
- Add body-aligned metadata, explicit pitch-value imputation, and complete token-index, time, track, pitch, and
  circle-of-fifths metadata
- Repair overlapping same-key MIDI retriggers into adjacent exportable notes and scale MIDI ticks with exact rational
  arithmetic
- Cache incremental grammar masks by compact state and merge already-sorted per-track note streams during tokenisation
- Preclassify vocabulary categories for faster cold constrained-decoding masks and benchmark realistic cold and warm
  state traces separately
- Add context-aware bar slices with an opt-out for raw event-window slicing
- Add a repeatable local release benchmark and a documented 10% regression policy
- Add concise guides, an API reference, executable examples, and automated GitHub Pages publication
- Export the typed `Key` enum with clear major and minor key names from the top-level package

### Changed

- Preserve major/minor mode for all valid MIDI key signatures
- Compare all represented event timing and values in sequence equality
- Lock reproducible development, documentation, and CI dependencies while retaining bounded dependency ranges for
  library consumers
- Test source and installed-wheel behavior on Python 3.11 through 3.14
- Expose CPU and GPU Nix development shells for every supported Python version from 3.11 through 3.14
- Test source, wheel, and sdist behavior before publication, with the release job gated by the full Python matrix
- Require at least 95% source coverage, strict type checks, strict documentation builds, and executable examples
- Make `tokenise()` consistently return complete `sta ... sto` streams
- Use British spelling consistently throughout the tokenisation API
- Preserve note-off velocity and the complete standard MIDI time-signature payload in immutable values
- Require complete canonical streams during detokenisation and normalise semantically equivalent note-value configs
- Validate constraint candidates without materialising unused immutable states
- Use allocation-light exact integer arithmetic for quantisation and bar-length calculations
- Use a musically systematic default duration set covering common straight, triplet, and dotted values from a
  sixteenth-note triplet through a whole note while keeping corpus-specific duration vocabularies explicitly
  configurable

### Fixed

- Reconstruct immutable tokenisers from their configuration when pickled so multiprocessing spawn workers can use
  them without serialising read-only lookup tables
- Prevent multichannel same-pitch notes from interfering during quantisation
- Preserve trailing MIDI silence through end-of-track timing
- Honour channel and program flags in similarity calculations
- Avoid mutating caller-owned sequences during tokenisation
- Omit the maximum bar position because the end-of-bar token represents complete bars without a redundant endpoint
- Preserve time-signature channels when copying bars
- Make the version helper work from installed wheels
- Validate collection element types before canonical sorting
- Reject booleans and malformed values in tokeniser configuration
- Reject duplicate vocabulary entries, excessive velocity bins, unknown token strings, and non-integral token IDs
- Reject ambiguous same-channel/same-pitch overlaps during MIDI export
- Close repaired grouped-track notes at their source-track endpoint
- Treat identical empty and program-only sequences as maximally similar
- Extend token endpoints through quantised note tails and prevent stopping while notes are still sounding
- Preserve terminal events in full slices and final split parts, and define zero-length slices as empty sequences
- Compare durations in musical time across PPQN values and reject raw-coordinate similarity across mismatched PPQN
- Reject MIDI format 2 and report every non-integral target-PPQN tick before lossless import
- Reject mixed-PPQN bar splitting and preserve auxiliary time-signature context across cached bar states
- Correct bar capacity checks that mixed quarter-note and tick units
- Keep meterless tokenisation on its implicit 4/4 grammar when the position vocabulary supports longer meters
- Include note-off velocity in canonical immutable note ordering
- Reject mutable or malformed incremental-state note keys before they can reach the constraint cache
- Reject unknown tokeniser configuration keys through the public error hierarchy
- Reject non-finite benchmark baselines instead of allowing them to bypass the release regression gate
- Make octave wrapping constant-time even for very large integer transpositions
- Reject invalid MIDI formats, out-of-range MIDI PPQN values, and unencodable track names before export
- Preserve the source order of same-tick state updates so lossless MIDI round trips cannot change their final value
- Replay ordered channel-state history in contextual bar slices so bank selection and RPN/NRPN commands retain meaning
- Diagnose same-tick channel-state/note ordering that the immutable model must canonicalise
- Classify malformed note-message fields as import errors even when no matching note is active
- Canonicalise manifest JSON and reject non-finite configuration values before fingerprint validation
- Validate resource-shaping parameters before allocating the vocabulary
- Bound position vocabularies to standard MIDI PPQN and the largest meter the codec can represent
- Reject pathological note-value magnitudes before constructing vocabulary text
- Ensure local benchmarks measure the checked-out source and preserve blocked comparison reports
- Keep package licence metadata valid under the PEP 639 build backend
- Use patched build-backend versions without known setuptools or wheel security advisories
