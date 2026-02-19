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


def load_from_file(path_settings: Path = None):
    if path_settings is None:
        path_settings = Path(__file__).parent.parent.joinpath("config/default_settings.json")

    with open(path_settings) as settings_file:
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


load_from_file()
