from __future__ import annotations

import enum


class TokeniserType(enum.Enum):
    STANDARD_MIDILIKE_TOKENISER = "standard_midilike_tokeniser"
    RELATIVE_MIDILIKE_TOKENISER = "relative_midilike_tokeniser"
    COF_MIDILIKE_TOKENISER = "cof_midilike_tokeniser"
    STANDARD_NOTELIKE_TOKENISER = "standard_notelike_tokeniser"
    LARGE_VOCABULARY_NOTELIKE_TOKENISER = "large_vocabulary_notelike_tokeniser"
    RELATIVE_NOTELIKE_TOKENISER = "relative_notelike_tokeniser"
    COF_NOTELIKE_TOKENISER = "cof_notelike_tokeniser"
    LARGE_VOCABULARY_COF_NOTELIKE_TOKENISER = "large_vocabulary_cof_notelike_tokeniser"
    GRIDLIKE_TOKENISER = "gridlike_tokeniser"
    TRANSPOSED_NOTELIKE_TOKENISER = "transposed_notelike_tokeniser"
