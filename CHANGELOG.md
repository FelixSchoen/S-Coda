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
- Add tokenisation support

### Changed

- Renamed project to `scoda` (stylised as `S-Coda`)
- Adopted `pyproject.toml`
- Reworked settings to use `settings.json` file
- Adapted `Sequence.from_midi_file` to be able to use opened MIDI files
- Deprecated `to_dataframe()` methods
- Absolute note array will now always be sorted by time and then pitch values (lower comes first)
- Reworked logging framework
- Reworked `get_messages_of_type()` to work with a list of message types
- Reworked `get_message_time_pairings()` to work with a list of message types

### Fixed

- Fix pytest configuration
- Fix imports for project compatability

## [1.0] - 2022-12-08

### Added

- Initial release

