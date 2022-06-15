# Parts per quarter note number, amount of ticks used for representation of a quarter note
PPQN = 24
# Amount of velocity bins to use. Note that any velocity smaller than the bound of the smallest bin will be mapped to
# the velocity of the smallest bin
VELOCITY_BINS = 8
# The maximum velocity value
MAX_VELOCITY = 127
NOTE_LOWER_BOUND = 21
NOTE_UPPER_BOUND = 108

# Maximum power of 2 defining upper length of notes, e.g., 8 corresponds to PPQN * 2^3, or double whole notes
NOTE_VALUE_UPPER_BOUND = 8
# Maximum power of 2 defining lower length of notes, e.g., 8 corresponds to PPQN / 2^3, or thirty-second notes
NOTE_VALUE_LOWER_BOUND = 8
# Amount of dots to allow for notes
DOTTED_ITERATIONS = 1
# All allowed tuplets, e.g. a value of (3, 2) allows (normal) triplets
VALID_TUPLETS = [(3, 2)]

# Regex for pattern recognition
PATTERN_LENGTH = 2
REGEX_PATTERN = r"(?=(?P<pattern>(?:[+-]\d+){{{p_len}}})(?:[+-]\d+)*(?P<end>(?P=pattern)(?:[+-]\d+)*?)+)"
REGEX_SUBPATTERN = r"^(?P<pattern>(?:[+-]\d+)+)(?P=pattern)+$"
# Amount of seconds after which greedy pattern matching is applied
PATTERN_MAX_SEARCH_DURATION = 5

ROOT_LOGGER = "scoda"

# Polynomials, generated using http://arachnoid.com
SCALE_X3 = [
    -7.7160500211448380e-015,
    2.6000000000002825e+000,
    -4.8000000000008844e+000,
    3.2000000000006108e+000
]
SCALE_LOGLIKE = [
    1.1211198309988962e-001,
    2.8168998527053071e+000,
    -3.0339213824085780e+000,
    1.1087028091894717e+000
]

# Difficulty settings
DIFF_NOTE_AMOUNT_UPPER_BOUND: float
DIFF_NOTE_AMOUNT_LOWER_BOUND: float
DIFF_NOTE_CLASSES_UPPER_BOUND: float
DIFF_NOTE_CLASSES_LOWER_BOUND: float
DIFF_NOTE_CONCURRENT_UPPER_BOUND: float
DIFF_NOTE_CONCURRENT_LOWER_BOUND: float
DIFF_NOTE_VALUES_UPPER_BOUND: float
DIFF_NOTE_VALUES_LOWER_BOUND: float
DIFF_DISTANCES_UPPER_BOUND: float
DIFF_DISTANCES_LOWER_BOUND: float
DIFF_PATTERN_COVERAGE_UPPER_BOUND: float
DIFF_PATTERN_COVERAGE_LOWER_BOUND: float


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
    global DIFF_NOTE_AMOUNT_UPPER_BOUND
    global DIFF_NOTE_AMOUNT_LOWER_BOUND
    global DIFF_NOTE_VALUES_LOWER_BOUND
    global DIFF_NOTE_VALUES_UPPER_BOUND
    global DIFF_NOTE_CONCURRENT_UPPER_BOUND
    global DIFF_NOTE_CONCURRENT_LOWER_BOUND
    global DIFF_DISTANCES_UPPER_BOUND
    global DIFF_DISTANCES_LOWER_BOUND
    global NOTE_VALUE_UPPER_BOUND
    global NOTE_VALUE_LOWER_BOUND
    global DOTTED_ITERATIONS
    global VALID_TUPLETS
    global DIFF_PATTERN_COVERAGE_UPPER_BOUND
    global DIFF_PATTERN_COVERAGE_LOWER_BOUND
    global DIFF_NOTE_CLASSES_UPPER_BOUND
    global DIFF_NOTE_CLASSES_LOWER_BOUND

    NOTE_VALUE_UPPER_BOUND = 8
    NOTE_VALUE_LOWER_BOUND = 8

    DOTTED_ITERATIONS = 1
    VALID_TUPLETS = [(3, 2)]

    DIFF_NOTE_AMOUNT_UPPER_BOUND = 3.5
    DIFF_NOTE_AMOUNT_LOWER_BOUND = 1

    DIFF_NOTE_CLASSES_UPPER_BOUND = 10 / 4
    DIFF_NOTE_CLASSES_LOWER_BOUND = 5 / 4

    DIFF_NOTE_CONCURRENT_UPPER_BOUND = 3
    DIFF_NOTE_CONCURRENT_LOWER_BOUND = 1

    DIFF_NOTE_VALUES_UPPER_BOUND = PPQN / (2 ** 2)  # Sixteenth
    DIFF_NOTE_VALUES_LOWER_BOUND = PPQN / (2 ** 0)  # Quarter

    DIFF_DISTANCES_UPPER_BOUND = 30
    DIFF_DISTANCES_LOWER_BOUND = 12

    DIFF_PATTERN_COVERAGE_UPPER_BOUND = 0
    DIFF_PATTERN_COVERAGE_LOWER_BOUND = 0.5


initialize_values()
