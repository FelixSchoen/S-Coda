# Parts per quarter note number, amount of ticks used for representation of a quarter note
PPQN = 24
# Amount of velocity bins to use. Note that any velocity smaller than the bound of the smallest bin will be mapped to
# the velocity of the smallest bin
VELOCITY_BINS = 8
# The maximum velocity value
MAX_VELOCITY = 127
NOTE_LOWER_BOUND = 21
NOTE_UPPER_BOUND = 108

# Polynomials, generated using http://arachnoid.com
SCALE_DIFF_NOTE_VALUES = [
    1.3333333333333333e+000,
    -5.5555555555555552e-002
]
SCALE_X3 = [
    -7.7160500211448380e-015,
    2.6000000000002825e+000,
    -4.8000000000008844e+000,
    3.2000000000006108e+000
]

# Difficulty settings
DIFF_NOTE_VALUES_UPPER_BOUND = PPQN / 2 ** 2 - PPQN / 2 ** 3 / 2
DIFF_NOTE_VALUES_LOWER_BOUND = PPQN
DIFF_DISTANCES_UPPER_BOUND = 30
DIFF_DISTANCES_LOWER_BOUND = 12


def set_ppqn(ppqn: int) -> None:
    """
    Sets the parts per quarter note value used by sCoda

    :param ppqn: Parts per quarter note value in ticks
    """
    if ppqn <= 0:
        raise ValueError("PPQN must be greater than 0")

    global PPQN
    PPQN = ppqn

    initialize_values()


def set_velocity_bins(velocity_bins: int) -> None:
    """
    Sets the amount of velocity bins used by sCoda

    :param velocity_bins: Amount of velocity bins to use
    """
    if velocity_bins <= 0 or velocity_bins > 128:
        raise ValueError("Invalid velocity bin amount")

    global VELOCITY_BINS
    VELOCITY_BINS = velocity_bins


def initialize_values() -> None:
    global DIFF_NOTE_VALUES_LOWER_BOUND
    global DIFF_NOTE_VALUES_UPPER_BOUND
    global DIFF_DISTANCES_UPPER_BOUND
    global DIFF_DISTANCES_LOWER_BOUND

    DIFF_NOTE_VALUES_UPPER_BOUND = PPQN / 2 ** 2 - PPQN / 2 ** 3 / 2
    DIFF_NOTE_VALUES_LOWER_BOUND = PPQN
    DIFF_DISTANCES_UPPER_BOUND = 30
    DIFF_DISTANCES_LOWER_BOUND = 12
