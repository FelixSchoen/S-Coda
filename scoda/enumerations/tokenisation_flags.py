from __future__ import annotations

import enum


class TokenisationFlags(enum.Enum):
    RUNNING_VALUE = "running_value"
    RUNNING_PITCH = "running_pitch"
    RUNNING_OCTAVE = "running_octave"
    RUNNING_TIME_SIG = "running_time_signature"
