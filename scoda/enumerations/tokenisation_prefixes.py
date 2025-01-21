from enum import Enum


class TokenisationPrefixes(Enum):
    PAD = "pad"
    START = "sta"
    STOP = "sto"
    BAR = "bar"
    REST = "rst"
    NOTE = "nte"
    INSTRUMENT = "ins"
    PITCH = "pit"
    VALUE = "val"
    VELOCITY = "vel"
    TIME_SIGNATURE = "tsg"
