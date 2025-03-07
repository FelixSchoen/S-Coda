from enum import Enum


class TokenisationPrefixes(Enum):
    PAD = "pad"
    START = "sta"
    STOP = "sto"
    BAR = "bar"
    REST = "rst"
    NOTE = "nte"
    TRACK = "trk"
    PITCH = "pit"
    VALUE = "val"
    VELOCITY = "vel"
    TIME_SIGNATURE = "tsg"
