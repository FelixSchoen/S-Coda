from sCoda.elements.bar import Bar


class Track:
    """
    Class representing a track, which is made of (multiple) bars.
    """

    def __init__(self, bars: [Bar], name: str = None) -> None:
        super().__init__()
        self._name = name
        self._bars = bars
