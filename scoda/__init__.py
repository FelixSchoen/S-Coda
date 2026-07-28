"""S-Coda's stable public API."""

from importlib.metadata import PackageNotFoundError, version

from scoda.core import (
    BarSpan,
    ControlChange,
    Event,
    KeySignature,
    Note,
    ProgramChange,
    Sequence,
    SequenceBuilder,
    Tempo,
    TimeSignature,
    bar_spans,
    split_bars,
)
from scoda.errors import (
    MidiError,
    MidiImportError,
    ScodaError,
    SequenceError,
    TokenisationError,
    ValidationError,
)
from scoda.midi_io import (
    MidiDiagnostic,
    MidiImportReport,
    MidiLoadResult,
    load_midi,
    save_midi,
    to_mido,
)
from scoda.music_theory import Key
from scoda.tokenisation import (
    NotelikeConfig,
    NotelikeTokeniser,
    TokeniserState,
    TokenMetadata,
    VocabularyManifest,
    create_tokeniser,
)

try:
    __version__ = version("scoda")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "3.0.0.dev0"

__all__ = [
    "BarSpan",
    "ControlChange",
    "Event",
    "KeySignature",
    "Key",
    "MidiDiagnostic",
    "MidiError",
    "MidiImportError",
    "MidiImportReport",
    "MidiLoadResult",
    "Note",
    "NotelikeConfig",
    "NotelikeTokeniser",
    "ProgramChange",
    "ScodaError",
    "Sequence",
    "SequenceBuilder",
    "SequenceError",
    "Tempo",
    "TimeSignature",
    "TokenisationError",
    "TokeniserState",
    "TokenMetadata",
    "ValidationError",
    "VocabularyManifest",
    "bar_spans",
    "create_tokeniser",
    "load_midi",
    "save_midi",
    "split_bars",
    "to_mido",
]
