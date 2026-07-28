"""Public exception hierarchy for S-Coda."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scoda.midi_io import MidiImportReport


class ScodaError(Exception):
    """Base class for all library-defined errors."""


class ValidationError(ScodaError, ValueError):
    """Raised when a public value violates a core invariant."""


class SequenceError(ScodaError):
    """Raised when a sequence transformation cannot be performed safely."""


class MidiError(ScodaError):
    """Base class for MIDI conversion errors."""


class MidiImportError(MidiError):
    """Raised when strict MIDI import encounters malformed input."""

    def __init__(self, message: str, report: MidiImportReport | None = None) -> None:
        super().__init__(message)
        self.report = report


class TokenisationError(ScodaError):
    """Raised for invalid tokens, configurations, or token streams."""
