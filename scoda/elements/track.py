from __future__ import annotations

import warnings
from copy import deepcopy

from scoda.elements.bar import Bar
from scoda.enumerations.message_type import MessageType
from scoda.exceptions.track_exception import TrackException
from scoda.sequences.sequence import Sequence


class Track:
    """Class representing a track, which is made of (multiple) bars.
    """

    def __init__(self, bars: [Bar], name: str = None) -> None:
        super().__init__()
        self.name = name
        self.bars = bars
        self.program = None

        seq = Bar.to_sequence(bars)
        program_changes = [msg for msg in seq.messages_rel() if msg.message_type == MessageType.PROGRAM_CHANGE]
        if len(program_changes) > 0:
            if not all(msg.program == program_changes[0].program for msg in program_changes):
                raise TrackException("Type of instrument inconsistent")
            self.program = program_changes[0].program

    def copy(self) -> Track:
        cpy = self.__class__(self.bars.copy(), self.name)
        return cpy

    def __copy__(self):
        warnings.warn("Use .copy() instead of copy.copy() for better performance.", UserWarning)
        return self.copy()

    def __deepcopy__(self, memo):
        warnings.warn("Use .copy() instead of copy.deepcopy() for better performance.", UserWarning)
        return self.copy()

    def to_sequence(self) -> Sequence:
        return Bar.to_sequence(self.bars)
