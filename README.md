# S-Coda

[![GitHub Release](https://img.shields.io/github/v/release/FelixSchoen/S-Coda?include_prereleases&label=Latest%20Release)](https://github.com/FelixSchoen/S-Coda/releases)
[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/FelixSchoen/S-Coda/scoda_test.yml?label=Build)](https://github.com/FelixSchoen/S-Coda/actions/workflows/scoda_test.yml)
[![Python Version](https://img.shields.io/badge/Python-3.11--3.14-blue)](https://www.python.org/)

S-Coda is a typed Python library for deterministic symbolic-music processing. It provides immutable musical values,
validated MIDI import and export, sequence transformations, bar splitting, canonical tokenisation, vocabulary
fingerprints, and incremental decoding constraints for machine-learning workflows.

## Installation

Install the current release from [PyPI](https://pypi.org/project/scoda/):

```bash
python -m pip install scoda
```

S-Coda supports Python 3.11 through 3.14 and has one core dependency, Mido.

## Quick start

```python
from scoda import Note, NotelikeConfig, NotelikeTokeniser, Sequence, save_midi

sequence = Sequence(
    notes=(Note(0, 24, 60, 96), Note(24, 48, 64, 88)),
    duration_ticks=96,
    ticks_per_quarter=24,
)
sequence = sequence.quantise_and_normalise((3, 6, 12, 24), (6, 12, 24))

tokeniser = NotelikeTokeniser(NotelikeConfig(note_values=(6, 12, 24), velocity_bins=127))
tokens = tokeniser.tokenise((sequence,))
token_ids = tokeniser.encode(tokens)
assert tokeniser.decode(token_ids) == tokens
assert tokeniser.detokenise(tokens) == (sequence,)

save_midi((sequence,), "output.mid")
```

Transformations return new values and never mutate their input. MIDI repairs are explicit diagnostics, token streams
have a canonical grammar, and each vocabulary has a deterministic manifest and SHA-256 fingerprint.

## Documentation

The complete guide and API reference are available at
[felixschoen.github.io/S-Coda](https://felixschoen.github.io/S-Coda/). It covers:

- immutable sequences and transformations;
- MIDI repair, strict, and lossless import policies;
- bar splitting and carried musical context;
- token framing, metadata, manifests, and constrained decoding;
- reproducible experiment persistence and release benchmarks.

Development and release commands are documented in [the benchmark guide](benchmarks/README.md) and the hosted
documentation. The supported public API consists of names exported directly from `scoda`.

## Citing

If you use S-Coda in research, please cite:

```bibtex
@inproceedings{Schoen.2023,
  author       = {Felix Sch{\"{o}}n and Hans Tompits},
  title        = {{PAUL-2:} An Upgraded Transformer-Based Redesign of the Algorithmic Composer {PAUL}},
  booktitle    = {22nd International Conference of the Italian Association for Artificial Intelligence ({AIxIA 2023})},
  series       = {Lecture Notes in Computer Science},
  volume       = {14318},
  pages        = {278--291},
  publisher    = {Springer},
  year         = {2023},
  doi          = {10.1007/978-3-031-47546-7\_19}
}
```

See [CHANGELOG.md](CHANGELOG.md) for release history.
