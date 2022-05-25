from sCoda.elements.bar import Bar


class Track:
    """
    Class representing a track, which is made of (multiple) bars.
    """

    def __init__(self, bars: [Bar], name: str = None) -> None:
        super().__init__()
        self.name = name
        self.bars = bars

    def __copy__(self):
        bars = []
        for bar in self.bars:
            bars.append(bar.__copy__())

        cpy = Track(bars, self.name)

        return cpy
