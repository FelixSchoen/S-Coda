from sCoda.elements.bar import Bar


class Track:
    """
    Class representing a track, which is made of (multiple) bars.
    """

    def __init__(self, bars: [Bar], name: str = None) -> None:
        super().__init__()
        self._name = name
        self._bars = bars

    def __copy__(self):
        bars = []
        for bar in self._bars:
            bars.append(bar.__copy__())

        cpy = Track(bars, self._name)

        return cpy

    @property
    def name(self) -> str:
        return self._name

    @property
    def bars(self) -> [Bar]:
        return self._bars
