from __future__ import annotations

import enum


class TokeniserType(enum.Enum):
    STANDARD_MIDILIKE_TOKENISER = "standard_midilike_tokeniser"
    STANDARD_NOTELIKE_TOKENISER = "standard_notelike_tokeniser"
    LARGE_DICTIONARY_NOTELIKE_TOKENISER = "large_dictionary_notelike_tokeniser"
    COF_NOTELIKE_TOKENISER = "cof_notelike_tokeniser"
    LARGE_DICTIONARY_COF_NOTELIKE_TOKENISER = "large_dictionary_cof_notelike_tokeniser"
    GRIDLIKE_TOKENISER = "gridlike_tokeniser"
    TRANSPOSED_NOTELIKE_TOKENISER = "transposed_notelike_tokeniser"
