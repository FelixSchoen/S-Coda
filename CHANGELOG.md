# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Setup CI pipeline
- Implement `get_representation()` methods
- Add changelog
- Add equivalence test for absolute sequences
- Add support for MIDI-like tokenisation
- Add support for note-like tokenisation (standard, circle of fifths, and large dictionary)
- Add support for gridlike tokenisation
- Add support for transposed gridlike tokenisation

### Changed

- Renamed project to `scoda` (stylised as `S-Coda`)
- Adopted `pyproject.toml`
- Adapted `Sequence.from_midi_file()` to be able to use opened MIDI files
- Deprecated `to_dataframe()` methods
- Absolute note list will now always be sorted by time and then pitch values (lower comes first)
- Reworked settings to use `settings.json` file
- Reworked logging framework
- Reworked `get_messages_of_type()` to work with a list of message types
- Reworked `get_message_time_pairings()` to work with a list of message types
- Reworked `adjust()` to remove invalid notes and only consolidate (instead of split up to chunks of `PPQN`) wait messages
- Renamed `adjust()` to `normalise()`
- Renamed `Sequence.from_midi_file()` to `Sequence.sequences_load()`
- Renamed `Sequence.split_to_bars` to `Sequence.sequences_split_bars()`

### Fixed

- Fix pytest configuration
- Fix imports for project compatability
- Fix transposing bar not transposing its key signature
- Fix calculation of dotted note values

## [1.0] - 2022-12-08

### Added

- Initial release

