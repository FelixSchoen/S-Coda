# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.7.1] - 2026-04-23

### Added

- Add `info_instrument` to multi-track notelike tokeniser metadata, using `0` for track-agnostic tokens and `1..N` for track-specific note and `TRACK` tokens
- Add regression coverage for running-track instrument assignments in `get_info()`

## [2.7] - 2026-02-19

### Added

- Add regression tests for all prior bugfixes in `TestBugfixValidation`

### Changed

- Extend tokenisation roundtrip tests to cover `flag_absolute_bar_position=False`

### Removed

- Remove all difficulty computation code (`DIFF_DUAL_*` parameters, `SCALE_CUBIC`/`SCALE_LOGLIKE` polynomials, `regress()`, `minmax()`) from settings, config, and utilities

### Fixed

- Fix `ReadOnlyMessage.copy()` raising `TypeError` due to incorrect constructor dispatch
- Fix `Key.transpose_key()` returning `None` when transposing by a multiple of 12
- Fix `split()` losing notes when two channels play the same pitch simultaneously
- Fix `get_info()` not updating `prv_pitch` when encountering a `PITCH` token
- Fix note messages in `MidiTrack.to_mido_track()` not writing the correct channel
- Fix `Message.equivalent()` silently returning `True` for messages with different attribute sets

## [2.6] - 2026-02-02

### Added
- Comprehensive test suite for edge cases

### Changed
- Improve code quality and fix minor code smells

### Fixed
- Prevent crashes on empty sequences
- Fix internal logic in `normalise_relative`
- Ensure similarity flags are correctly passed

## [2.5] - 2026-01-31

### Added

- Add nix flake support

### Changed

- Rework hierarchy transitions for tokenisation

## [2.4] - 2025-03-18

### Added

- Implement read-only messages
- Provide way to invalidate sequences via `Sequence.invalidate_abs()` and `Sequence.invalidate_rel()` methods
- Provide way to refresh stale sequences via `Sequence.refresh()`

### Changed

- Rework copying of elements

## [2.3] - 2025-03-17

### Changed

- Provide way to safely modify sequence messages via `Sequence.messages_abs()` and `Sequence.messages_rel()`

## [2.2] - 2025-03-07

### Changed

- Adapt S-Coda to support _channels_ for messages
- Rework tokenisation approaches

## [2.1] - 2025-01-20

### Added

- Add tokenisation methods

### Changed

- Re-release

## [1.0] - 2022-12-08

### Added

- Initial release
