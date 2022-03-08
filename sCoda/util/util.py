import math

import numpy as np

from sCoda.settings import MAX_VELOCITY, VELOCITY_BINS


def digitise_velocity(velocity_unquantised: int) -> int:
    """ Digitises velocity to bins.

    Digitises the given velocity based on the settings of sCoda. Returns a value that corresponds to one of the bins,
    but not the index of the bin itself. E.g., the value of 33 could be quantised to 32 with bins of size 16.
    In this case, the value of 32 would be returned, rather than the index 2 (of the second bin).

    Args:
        velocity_unquantised: The initial velocity

    Returns: The quantised value

    """
    if velocity_unquantised == 0:
        return velocity_unquantised

    return velocity_from_bin(bin_from_velocity(velocity_unquantised))


def velocity_from_bin(bin_index: int) -> int:
    """ Returns the velocity defined by the bin.

    Args:
        bin_index: Index of the bin to get the velocity for

    Returns: The corresponding velocity

    """
    bin_size = round(MAX_VELOCITY / VELOCITY_BINS)
    return int(min(MAX_VELOCITY, (bin_index + 1) * bin_size))


def bin_from_velocity(velocity: int) -> int:
    """ Returns the bin defined by the velocity.

    Args:
        velocity: The velocity to sort into a bin

    Returns: The corresponding bin

    """
    if velocity <= 0 or velocity > MAX_VELOCITY:
        raise ValueError("Velocity not contained in any bag")

    bin_size = round(MAX_VELOCITY / VELOCITY_BINS)
    bins = [min(MAX_VELOCITY, ((i + 1) * bin_size) + bin_size / 2) for i in range(0, VELOCITY_BINS)]

    return np.digitize(velocity, bins, right=True).item(-1)


def b_insort(collection: list, x) -> None:
    lo = 0
    hi = len(collection)

    while lo < hi:
        mid = (lo + hi) // 2
        if x.time < collection[mid].time:
            hi = mid
        else:
            lo = mid + 1

    collection.insert(lo, x)


def find_minimal_distance(element, collection) -> int:
    """ Finds the element in the collection with the minimal distance to the given element.

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


# From http://arachnoid.com
def regress(x, terms):
    t = 1
    r = 0
    for c in terms:
        r += c * t
        t *= x
    return r


# From https://stackoverflow.com/questions/43099542/python-easy-way-to-do-geometric-mean-in-python
def geo_mean(iterable):
    a = np.array(iterable)
    return a.prod() ** (1.0 / len(a))
