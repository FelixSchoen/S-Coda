# S-Coda

[![GitHub Release](https://img.shields.io/github/v/release/FelixSchoen/S-Coda?include_prereleases&label=Latest%20Release)](https://github.com/FelixSchoen/S-Coda/releases)
[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/FelixSchoen/S-Coda/scoda_test.yml?label=Build)](https://github.com/FelixSchoen/S-Coda/actions/workflows/scoda_test.yml)
[![Python Version](https://img.shields.io/badge/Python%20Version-3.11-blue)](https://www.python.org/downloads/release/python-3119/)

[![DOI](https://img.shields.io/badge/DOI-10.34726%2Fhss.2023.103585-blue)](https://doi.org/10.34726/hss.2023.103585)
[![DOI](https://img.shields.io/badge/DOI-10.1007%2F978--3--031--47546--7_19-blue)](https://doi.org/10.1007/978-3-031-47546-7_19)

## Overview

S-Coda is a Python library for handling MIDI files.
It is written with the purpose of machine learning tasks in mind.
S-Coda supports a plethora of different MIDI manipulation operations, such as:

- quantisation of notes
- quantisation of note lengths
- splitting sequences into bars
- transposing of sequences
- creating piano-roll visualisations of pieces
- tokenisation of sequences

S-Coda was used in our project [PAUL-2](https://github.com/FelixSchoen/PAUL-2) to process MIDI files.
For information about how to use S-Coda we refer to chapter 5 of the [thesis](https://doi.org/10.34726/hss.2023.103585)
in which S-Coda was introduced.
Note that this thesis refers to version 1.0 of S-Coda, which has since received major overhauls.

## Installation

We recommend installing S-Coda from [PyPI](https://pypi.org/project/scoda/) using pip:

```pip install scoda```

## Changelog

See [`CHANGELOG.md`](https://github.com/FelixSchoen/S-Coda/blob/main/CHANGELOG.md) for a detailed changelog.

## Usage

### Example

We refer to the aforementioned thesis for a more in-depth guide on how to use S-Coda.
We provide a short listing on how to use basic S-Coda functions, which is up-to-date as of version 2.4.0.:

```python
    # Load sequence, choose correct track (often first track contains only meta messages)
sequence = Sequence.sequences_load(file_path=RESOURCE_BEETHOVEN)[1]

# Quantise the sequence to sixteenths and sixteenth triplets (standard values)
sequence.quantise_and_normalise()

# Split the sequence into bars based on the occurring time signatures
bars = Sequence.sequences_split_bars([sequence], meta_track_index=0)[0]

# Prepare tokeniser and output tokens
tokeniser = MultiTrackLargeVocabularyNotelikeTokeniser(num_tracks=1)
tokens = []

# Tokenise all bars in the sequence
for bar in bars:
    tokens.extend(tokeniser.tokenise([bar.sequence]))

# Convert to a numeric representation
encoded_tokens = tokeniser.encode(tokens)

# (Conduct ML operations on tokens)
encoded_tokens = encoded_tokens

# Convert back to token representation
decoded_tokens = tokeniser.decode(encoded_tokens)

# Create sequence from tokens
detokenised_sequences = tokeniser.detokenise(decoded_tokens)

# Save sequence
detokenised_sequences[0].save("../out/generated_sequence.mid")
```

### Implementational Details

S-Coda is built around the `Sequence` class, which represents a musical sequence.
The `Sequence` object is a wrapper for two internal classes, `AbsoluteSequence` and `RelativeSequence`, which represent
music in two different ways.
For the absolute sequences, the elements of the sequences are annotated with their absolute points in time within the
sequence, while for the relative sequence elements specify the time between events.
These two representations are used internally for different operations.
The `Sequence` object abstracts away the differences between these two representations and provides the user with a
unified experience.

The atomic element of S-Coda is the `Message`, which is comparable to a MIDI event.
Messages have a `MessageType`, denoting the type of the message, and several other fields depending on which type of
message it is.
For example, a message of type `NOTE_ON` will have a `note` field, which denotes the pitch number of the note that it
represents.

Note that directly editing single messages or the messages of a sequence is possible, but not recommended, as it can
lead to inconsistencies in the `Sequence` object.
If you still need to do so, make sure to invalidate either the absolute or relative internal representation (using
`Sequence.invalidate_abs()` and `Sequence.invalidate_rel()`) after directly editing messages.
This is _not_ required when modifying the sequence using the functions provided by `Sequence`, as staleness of the
internal representations is kept track of this way.

# Citing

If you use S-Coda in your research, please cite the following paper:

```bibtex
@inproceedings{Schoen.2023,
  author       = {Felix Sch{\"{o}}n and
                  Hans Tompits},
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