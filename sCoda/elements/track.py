from sCoda.elements.bar import Bar


class Track:
    """
    Class representing a track, which is made of (multiple) bars.
    """

    def __init__(self, bars: [Bar], name: str = None) -> None:
        super().__init__()
        self._name = name
        self._bars = bars

    @property
    def name(self):
        return self._name

    @property
    def bars(self):
        return self._bars
