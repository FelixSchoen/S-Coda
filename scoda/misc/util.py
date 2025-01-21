import math

import numpy as np

from scoda.elements.message import Message
from scoda.settings.settings import VELOCITY_MAX, VELOCITY_BINS, PPQN, NOTE_VALUE_UPPER_BOUND, NOTE_VALUE_LOWER_BOUND, \
    VALID_TUPLETS, DOTTED_ITERATIONS


def bin_velocity(velocity: int, bins: list[int] = None) -> int:
    """Returns the bin defined by the velocity.

    Args:
        velocity: The velocity to sort into a bin

    Returns: The corresponding bin

    """
    if bins is None:
        bins = get_velocity_bins()

    return np.digitize(velocity, bins, right=True).item(-1)


def get_velocity_bins(velocity_max=None, velocity_bins=None):
    if velocity_max is None:
        velocity_max = VELOCITY_MAX
    if velocity_bins is None:
        velocity_bins = VELOCITY_BINS

    bin_size = round(velocity_max / velocity_bins)
    bins = [min(velocity_max, ((i + 1) * bin_size) + bin_size / 2) for i in range(0, velocity_bins)]

    return bins


def binary_insort(collection: list, message: Message) -> None:
    """Sorts the given message into the correct position in the already sorted list.

    Args:
        collection: A list of messages that is already sorted
        message: The message to insert

    """
    lo = 0
    hi = len(collection)

    while lo < hi:
        mid = (lo + hi) // 2
        if message.time < collection[mid].time:
            hi = mid
        else:
            lo = mid + 1

    collection.insert(lo, message)


def digitise_velocity(velocity_unquantised: int) -> int:
    """Digitises velocity to bins.

    Digitises the given velocity based on the settings of scoda. Returns a value that corresponds to one of the bins,
    but not the index of the bin itself. E.g., the value of 33 could be quantised to 32 with bins of size 16.
    In this case, the value of 32 would be returned, rather than the index 2 (of the second bin).

    Args:
        velocity_unquantised: The initial velocity

    Returns: The quantised value

    """
    if velocity_unquantised == 0:
        return velocity_unquantised

    return velocity_from_bin(bin_velocity(velocity_unquantised))


def find_minimal_distance(element, collection) -> int:
    """Finds the element in the collection with the minimal distance to the given element.

    Ties are broken using the indices of the collection, earlier elements will be preferred.

    Args:
        element: The element to compare against
        collection: The collection with candidate values

    Returns: The index of the found element

    """
    distance = math.inf
    index = 0

    for i, candidate in enumerate(collection):
        candidate_distance = abs(candidate - element)
        if candidate_distance < distance:
            distance = candidate_distance
            index = i
            if distance == 0:
                return index

    return index


def get_default_step_sizes(upper_bound_shift=0, lower_bound_shift=0):
    quantise_parameters = get_note_durations(1*2**upper_bound_shift, 4*2**lower_bound_shift)
    quantise_parameters += get_tuplet_durations(quantise_parameters, 3, 2)
    step_sizes = quantise_parameters

    return step_sizes


def get_default_note_values():
    normal_durations = get_note_durations(NOTE_VALUE_UPPER_BOUND, NOTE_VALUE_LOWER_BOUND)
    triplet_durations = []
    for valid_tuplet in VALID_TUPLETS:
        triplet_durations.extend(get_tuplet_durations(normal_durations, valid_tuplet[0], valid_tuplet[1]))
    dotted_durations = get_dotted_note_durations(normal_durations, DOTTED_ITERATIONS)
    possible_durations = normal_durations + triplet_durations + dotted_durations

    return possible_durations


def get_note_durations(upper_bound_multiplier: int, lower_bound_divisor: int, base_value: int = PPQN) -> [int]:
    """Generates an array of valid note durations in ticks with regard to the PPQN.

    Automatically generates the duration of notes in ticks using the given parameters, by multiplying or dividing the
    given base value with the upper and lower bounds. In order to generate note values up to half notes with the
    standard base value of the PPQN, an upper bound of 2 has to be selected, with which the base value will be
    multiplied. In order to generate note values down to sixteenth notes with the standard base value of the PPQN,
    a lower bound of 4 as to be selected, with which the base value will be divided by.

    Args:
        upper_bound_multiplier: Maximum multiplier of the given base value
        lower_bound_divisor: Maximum divisor of the given base value
        base_value: Amount of ticks for the base value, upon which calculation is based

    Returns: An array of note values in ticks

    """
    durations = []

    i = upper_bound_multiplier
    while i >= 1:
        durations.append(int(i * base_value))
        i /= 2

    j = 2
    while j <= lower_bound_divisor:
        durations.append(int(base_value / j))
        j *= 2

    return durations


def get_tuplet_durations(note_durations, ratio_numerator, ratio_denominator) -> [int]:
    """Generates tuplet durations from a ratio and given note durations.

    Generates tuplet values for each duration in the given array, by dividing by the denominator and multiplying with
    the numerator.

    Args:
        note_durations: A base array of valid note durations
        ratio_numerator: The numerator of the tuplet
        ratio_denominator: The denominator of the tuplet

    Returns: The generated tuplet lengths in ticks

    """
    tuplet_durations = []

    for note_duration in note_durations:
        tuplet_durations.append(int((note_duration * ratio_denominator) / ratio_numerator))

    return tuplet_durations


def get_dotted_note_durations(note_durations, dotted_iterations) -> [int]:
    """Generates dotted note durations from an initial array of note durations.

    For each duration in the given array, creates up to the specified amount of iterations dotted values. E.g.,
    if `dotted_iterations` were set to 2, durations for single and twice dotted notes would be generated from the
    given array.

    Args:
        note_durations: A base array of valid note durations
        dotted_iterations: The largest amount of dots to allow for notes

    Returns: The generated note lengths in ticks

    """
    dotted_durations = []

    for dotted_note_iteration in range(dotted_iterations):
        for note_duration in note_durations:
            candidate_duration = note_duration * (1 + (1 - 1 / (2 ** (dotted_note_iteration + 1))))
            if candidate_duration.is_integer():
                dotted_durations.append(int(candidate_duration))

    return dotted_durations


def minmax(minimum, maximum, value):
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


# From http://arachnoid.com
def regress(x, terms):
    """Calculates f(x) based on x and the coefficients given by `terms`.

    Args:
        x: Input value
        terms: Coefficients, starting with x^0

    Returns:

    """
    t = 1
    r = 0
    for c in terms:
        r += c * t
        t *= x
    return r


def simple_regression(x1, y1, x2, y2, value):
    c_1 = (y2 - y1) / (x2 - x1)
    c_0 = y1 - x1 * c_1
    return c_1 * value + c_0


def velocity_from_bin(bin_index: int) -> int:
    """Returns the velocity defined by the bin.

    Args:
        bin_index: Index of the bin to get the velocity for

    Returns: The corresponding velocity

    """
    bin_size = round(VELOCITY_MAX / VELOCITY_BINS)
    return int(min(VELOCITY_MAX, (bin_index + 1) * bin_size))
