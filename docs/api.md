# API reference

Only names exported directly from `scoda` are part of the supported public API.

## Musical values and transformations

::: scoda.core
    options:
      members:
        - Note
        - TimeSignature
        - KeySignature
        - Tempo
        - ControlChange
        - ProgramChange
        - BarSpan
        - Sequence
        - SequenceBuilder
        - bar_spans
        - split_bars

## Music theory

::: scoda.music_theory.Key

## MIDI

::: scoda.midi_io
    options:
      members:
        - MidiDiagnostic
        - MidiImportReport
        - MidiLoadResult
        - load_midi
        - to_mido
        - save_midi

## Tokenisation

::: scoda.tokenisation.tokeniser
    options:
      members:
        - NotelikeConfig
        - NotelikeTokeniser
        - TokeniserState
        - TokenMetadata
        - VocabularyManifest
        - create_tokeniser

## Errors

::: scoda.errors
