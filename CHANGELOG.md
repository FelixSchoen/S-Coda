# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1]

### Added

- Add changelog
- Add equivalence test for absolute sequences
- Add tokenisation support
- Add `quantise_and_normalise()` method for sequences
- Add `save()` method for compositions

### Changed

- Change Python version from 3.10 to 3.11
- Rename project to `scoda` (stylised as `S-Coda`)
- Adapt `pyproject.toml`
- Rename `get_sequence_length()` to `get_sequence_duration()`

### Deprecated

- Deprecate `to_dataframe()` methods

### Fixed

- Fix transposing bar not transposing its key signature
- Fix calculation of dotted note values

## [1.0] - 2022-12-08

### Added

- Initial release

