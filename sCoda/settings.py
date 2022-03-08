# Parts per quarter note number, amount of ticks used for representation of a quarter note
PPQN = 24
# Amount of velocity bins to use. Note that any velocity smaller than the bound of the smallest bin will be mapped to
# the velocity of the smallest bin
VELOCITY_BINS = 8
# The maximum velocity value
MAX_VELOCITY = 127
POSSIBLE_NOTE_LENGTHS = [8 * PPQN, 4 * PPQN, 2 * PPQN, PPQN]
NOTE_LOWER_BOUND = 21
NOTE_UPPER_BOUND = 108

# Polynomials, generated using http://arachnoid.com
SCALE_X3 = [
    -5.7835680689066749e-015,
    2.6806722689079381e+000,
    -5.0420168067236864e+000,
    3.3613445378157629e+000
]


def set_ppqn(ppqn: int) -> None:
    """
    Sets the parts per quarter note value used by sCoda

    :param ppqn: Parts per quarter note value in ticks
    """
    if ppqn <= 0:
        raise ValueError("PPQN must be greater than 0")

    global PPQN
    PPQN = ppqn


def set_velocity_bins(velocity_bins: int) -> None:
    """
    Sets the amount of velocity bins used by sCoda

    :param velocity_bins: Amount of velocity bins to use
    """
    if velocity_bins <= 0 or velocity_bins > 128:
        raise ValueError("Invalid velocity bin amount")

    global VELOCITY_BINS
    VELOCITY_BINS = velocity_bins
