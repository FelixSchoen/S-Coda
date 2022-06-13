from sCoda.elements.bar import Bar
from sCoda.elements.message import MessageType
from sCoda.exception.exceptions import TrackException


class Track:
    """
    Class representing a track, which is made of (multiple) bars.
    """

    def __init__(self, bars: [Bar], name: str = None) -> None:
        super().__init__()
        self.name = name
        self.bars = bars
        self.program = None

        seq = Bar.to_sequence(bars)
        program_changes = [msg for msg in seq.rel.messages if msg.message_type == MessageType.program_change]
        if len(program_changes) > 0:
            if not all(msg.program == program_changes[0].program for msg in program_changes):
                raise TrackException("Type of instrument inconsistent")
            self.program = program_changes[0].program

    def __copy__(self):
        bars = []
        for bar in self.bars:
            bars.append(bar.__copy__())

        cpy = Track(bars, self.name)

        return cpy
