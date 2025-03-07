import json
from pathlib import Path

# General settings

"""Parts per quarter note, amount of ticks used for the representation of a quarter note"""
PPQN: int
"""Maximum velocity value, velocity values usually range from 0 to 127"""
VELOCITY_MAX: int
"""Amount of velocity bins to use, consolidating velocity values into `VELOCITY_BINS` bins"""
VELOCITY_BINS: int
"""MIDI value of lowest note"""
NOTE_LOWER_BOUND: int
"""MIDI value of highest note"""
NOTE_UPPER_BOUND: int
"""Maximum power of 2 defining lower length of notes, e.g., 8 corresponds to PPQN / 2^3, or thirty-second notes"""
NOTE_VALUE_LOWER_BOUND: int
"""Maximum power of 2 defining upper length of notes, e.g., 8 corresponds to PPQN * 2^3, or double whole notes"""
NOTE_VALUE_UPPER_BOUND: int
"""Amount of dots for dotted notes to consider"""
DOTTED_ITERATIONS: int
"""Considered tuplets, e.g., a value of (3, 2) allows for triplets"""
VALID_TUPLETS: list[tuple[int, int]]
"""The default time signature numerator"""
DEFAULT_TIME_SIGNATURE_NUMERATOR: int
"""The default time signature denominator"""
DEFAULT_TIME_SIGNATURE_DENOMINATOR: int

# Pattern Recognition

"""Minimum length of patterns to be considered"""
PATTERN_LENGTH_MIN: int
"""Amount of seconds after which greedy pattern matching is applied"""
PATTERN_SECONDS_SEARCH_DURATION: int
"""Regex used to find patterns"""
REGEX_PATTERN: str
"""Regex used to find subpatterns"""
REGEX_SUBPATTERN: str

# Difficulty Parameters

DIFF_DUAL_NOTE_AMOUNT_UPPER_BOUND: float
DIFF_DUAL_NOTE_AMOUNT_LOWER_BOUND: float
DIFF_DUAL_NOTE_CLASSES_UPPER_BOUND: float
DIFF_DUAL_NOTE_CLASSES_LOWER_BOUND: float
DIFF_DUAL_NOTE_CONCURRENT_UPPER_BOUND: float
DIFF_DUAL_NOTE_CONCURRENT_LOWER_BOUND: float
DIFF_DUAL_NOTE_VALUES_UPPER_BOUND: float
DIFF_DUAL_NOTE_VALUES_LOWER_BOUND: float
DIFF_DUAL_DISTANCES_UPPER_BOUND: float
DIFF_DUAL_DISTANCES_LOWER_BOUND: float
DIFF_DUAL_PATTERN_COVERAGE_UPPER_BOUND: float
DIFF_DUAL_PATTERN_COVERAGE_LOWER_BOUND: float
DIFF_DUAL_ACCIDENTALS_UPPER_BOUND: float
DIFF_DUAL_ACCIDENTALS_LOWER_BOUND: float

# Polynomials

"""Coefficients for cubic curve"""
SCALE_CUBIC: list[float]
"""Coefficients for loglike curve"""
SCALE_LOGLIKE: list[float]


def load_from_file(path_settings: Path = None):
    if path_settings is None:
        path_settings = Path(__file__).parent.parent.joinpath("config/default_settings.json")

    settings_file = open(path_settings)
    settings = json.load(settings_file)

    global PPQN
    global VELOCITY_MAX
    global VELOCITY_BINS
    global NOTE_LOWER_BOUND
    global NOTE_UPPER_BOUND
    global NOTE_VALUE_LOWER_BOUND
    global NOTE_VALUE_UPPER_BOUND
    global DOTTED_ITERATIONS
    global VALID_TUPLETS
    global DEFAULT_TIME_SIGNATURE_NUMERATOR
    global DEFAULT_TIME_SIGNATURE_DENOMINATOR

    global PATTERN_LENGTH_MIN
    global PATTERN_SECONDS_SEARCH_DURATION
    global REGEX_PATTERN
    global REGEX_SUBPATTERN

    global DIFF_DUAL_NOTE_AMOUNT_UPPER_BOUND
    global DIFF_DUAL_NOTE_AMOUNT_LOWER_BOUND
    global DIFF_DUAL_NOTE_CLASSES_UPPER_BOUND
    global DIFF_DUAL_NOTE_CLASSES_LOWER_BOUND
    global DIFF_DUAL_NOTE_CONCURRENT_UPPER_BOUND
    global DIFF_DUAL_NOTE_CONCURRENT_LOWER_BOUND
    global DIFF_DUAL_NOTE_VALUES_LOWER_BOUND
    global DIFF_DUAL_NOTE_VALUES_UPPER_BOUND
    global DIFF_DUAL_DISTANCES_UPPER_BOUND
    global DIFF_DUAL_DISTANCES_LOWER_BOUND
    global DIFF_DUAL_PATTERN_COVERAGE_UPPER_BOUND
    global DIFF_DUAL_PATTERN_COVERAGE_LOWER_BOUND
    global DIFF_DUAL_ACCIDENTALS_UPPER_BOUND
    global DIFF_DUAL_ACCIDENTALS_LOWER_BOUND

    global SCALE_CUBIC
    global SCALE_LOGLIKE

    PPQN = settings["general_settings"]["ppqn"]
    VELOCITY_MAX = settings["general_settings"]["velocity_max"]
    VELOCITY_BINS = settings["general_settings"]["velocity_bins"]
    NOTE_LOWER_BOUND = settings["general_settings"]["note_lower_bound"]
    NOTE_UPPER_BOUND = settings["general_settings"]["note_upper_bound"]
    NOTE_VALUE_LOWER_BOUND = settings["general_settings"]["note_value_lower_bound"]
    NOTE_VALUE_UPPER_BOUND = settings["general_settings"]["note_value_upper_bound"]
    DOTTED_ITERATIONS = settings["general_settings"]["dotted_iterations"]

    VALID_TUPLETS = []
    for tuplet in settings["general_settings"]["tuplets_valid"]:
        VALID_TUPLETS.append(tuple(tuplet))

    DEFAULT_TIME_SIGNATURE_NUMERATOR = settings["general_settings"]["default_time_signature_numerator"]
    DEFAULT_TIME_SIGNATURE_DENOMINATOR = settings["general_settings"]["default_time_signature_denominator"]

    PATTERN_LENGTH_MIN = settings["pattern_recognition"]["pattern_length_min"]
    PATTERN_SECONDS_SEARCH_DURATION = settings["pattern_recognition"]["pattern_seconds_search_duration"]
    REGEX_PATTERN = settings["pattern_recognition"]["regex_pattern"]
    REGEX_SUBPATTERN = settings["pattern_recognition"]["regex_subpattern"]

    DIFF_DUAL_NOTE_AMOUNT_UPPER_BOUND = settings["difficulty_parameters"]["dual_track_difficulty_parameters"][
        "diff_dual_note_amount_upper_bound"]
    DIFF_DUAL_NOTE_AMOUNT_LOWER_BOUND = settings["difficulty_parameters"]["dual_track_difficulty_parameters"][
        "diff_dual_note_amount_lower_bound"]
    DIFF_DUAL_NOTE_CLASSES_UPPER_BOUND = settings["difficulty_parameters"]["dual_track_difficulty_parameters"][
        "diff_dual_note_classes_upper_bound"]  # 10 / 4
    DIFF_DUAL_NOTE_CLASSES_LOWER_BOUND = settings["difficulty_parameters"]["dual_track_difficulty_parameters"][
        "diff_dual_note_classes_lower_bound"]  # 4 / 4
    DIFF_DUAL_NOTE_CONCURRENT_UPPER_BOUND = settings["difficulty_parameters"]["dual_track_difficulty_parameters"][
        "diff_dual_note_concurrent_upper_bound"]
    DIFF_DUAL_NOTE_CONCURRENT_LOWER_BOUND = settings["difficulty_parameters"]["dual_track_difficulty_parameters"][
        "diff_dual_note_concurrent_lower_bound"]
    DIFF_DUAL_NOTE_VALUES_UPPER_BOUND = PPQN / settings["difficulty_parameters"]["dual_track_difficulty_parameters"][
        "diff_dual_note_values_upper_bound"]  # (PPQN / (2 ** 2))
    DIFF_DUAL_NOTE_VALUES_LOWER_BOUND = PPQN / settings["difficulty_parameters"]["dual_track_difficulty_parameters"][
        "diff_dual_note_values_lower_bound"]  # (PPQN / (2 ** 0) + (PPQN / (2 ** 0))) / 2
    DIFF_DUAL_DISTANCES_UPPER_BOUND = settings["difficulty_parameters"]["dual_track_difficulty_parameters"][
        "diff_dual_distances_upper_bound"]
    DIFF_DUAL_DISTANCES_LOWER_BOUND = settings["difficulty_parameters"]["dual_track_difficulty_parameters"][
        "diff_dual_distances_lower_bound"]
    DIFF_DUAL_PATTERN_COVERAGE_UPPER_BOUND = settings["difficulty_parameters"]["dual_track_difficulty_parameters"][
        "diff_dual_pattern_coverage_upper_bound"]
    DIFF_DUAL_PATTERN_COVERAGE_LOWER_BOUND = settings["difficulty_parameters"]["dual_track_difficulty_parameters"][
        "diff_dual_pattern_coverage_lower_bound"]
    DIFF_DUAL_ACCIDENTALS_UPPER_BOUND = settings["difficulty_parameters"]["dual_track_difficulty_parameters"][
        "diff_dual_accidentals_upper_bound"]
    DIFF_DUAL_ACCIDENTALS_LOWER_BOUND = settings["difficulty_parameters"]["dual_track_difficulty_parameters"][
        "diff_dual_accidentals_lower_bound"]

    # Generated using http://arachnoid.com
    SCALE_CUBIC = settings["difficulty_parameters"]["polynomials"]["scale_cubic"]
    SCALE_LOGLIKE = settings["difficulty_parameters"]["polynomials"]["scale_loglike"]


load_from_file()
