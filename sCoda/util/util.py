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
