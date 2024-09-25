# S-Coda

[![GitHub Release](https://img.shields.io/github/v/release/FelixSchoen/S-Coda?include_prereleases&label=Latest%20Release)](https://github.com/FelixSchoen/S-Coda/releases)
[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/FelixSchoen/S-Coda/scoda_test.yml?label=Build)](https://github.com/FelixSchoen/S-Coda/actions/workflows/scoda_test.yml)
[![Python Version](https://img.shields.io/badge/Python%20Version-3.11-blue)](https://www.python.org/downloads/release/python-3119/)

[![DOI](https://img.shields.io/badge/DOI-10.34726%2Fhss.2023.103585-blue)](https://doi.org/10.34726/hss.2023.103585)
[![DOI](https://img.shields.io/badge/DOI-10.1007%2F978--3--031--47546--7_19-blue)](https://doi.org/10.1007/978-3-031-47546-7_19)

## Overview

S-Coda is a Python library for handling MIDI files.
S-Coda supports a plethora of different MIDI manipulation operations, such as:

- quantisation of notes
- quantisation of note lengths
- splitting sequences into bars
- transposing of sequences
- creating piano-roll visualisations of pieces
- judging the difficulty of pieces

S-Coda was used in our project [PAUL-2](https://github.com/FelixSchoen/PAUL-2) to process MIDI files.
For information about how to use S-Coda we refer to chapter 5 of the [thesis](https://doi.org/10.34726/hss.2023.103585) in which S-Coda was introduced.

## Installation

We recommend installing S-Coda from [PyPI](https://pypi.org/project/scoda/) using pip:

```pip install scoda```

## Changelog

See [`CHANGELOG.md`](https://github.com/FelixSchoen/S-Coda/blob/main/CHANGELOG.md) for a detailed changelog.

## Usage

We refer to the aforementioned thesis for a more in-depth guide on how to use S-Coda.
We provide a short listing on how to use basic S-Coda functions:

```python
    # Load sequence, choose correct track (often first track contains only meta messages)
    sequence = Sequence.sequences_load(file_path=RESOURCE_BEETHOVEN)[1]

    # Quantise the sequence to thirty-seconds and thirty-second triplets (standard values)
    sequence.quantise_and_normalise()

    # Split the sequence into bars based on the occurring time signatures
    bars = Sequence.sequences_split_bars([sequence], meta_track_index=0)[0]

    # Prepare tokeniser and output tokens
    tokeniser = StandardNotelikeTokeniser(running_value=True, running_pitch=True, running_time_sig=True)
    tokens = []
    difficulties = []

    # Tokenise all bars in the sequence and calculate their difficulties
    for bar in bars:
        tokens.extend(tokeniser.tokenise(bar.sequence))
        difficulties.append(bar.sequence.difficulty())

    # (Conduct ML operations on tokens)
    tokens = tokens

    # Create sequence from tokens
    detokenised_sequence = tokeniser.detokenise(tokens)

    # Save sequence
    detokenised_sequence.save("out/generated_sequence.mid")
```