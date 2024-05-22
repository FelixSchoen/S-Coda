from base import *
from scoda.tokenisation.gridlike_tokenisation import GridlikeTokeniser
from scoda.tokenisation.midilike_tokenisation import MidilikeTokeniser
from scoda.tokenisation.notelike_tokenisation import CoFNotelikeTokeniser, StandardNotelikeTokeniser, \
    LargeDictionaryNotelikeTokeniser
from scoda.tokenisation.transposed_notelike_tokenisation import TransposedNotelikeTokeniser


@pytest.mark.parametrize("path_resource, track", zip(RESOURCES, [0, 0, 1, 1]))
@pytest.mark.parametrize("running_value", [True, False])
@pytest.mark.parametrize("running_pitch", [True, False])
@pytest.mark.parametrize("running_time_sig", [True, False])
def test_roundtrip_standard_notelike_tokenisation(path_resource, track, running_value, running_pitch,
                                                  running_time_sig):
    tokeniser = StandardNotelikeTokeniser(running_value=running_value, running_pitch=running_pitch,
                                          running_time_sig=running_time_sig)

    _test_roundtrip_tokenisation(tokeniser, path_resource, track)


@pytest.mark.parametrize("path_resource, track", zip(RESOURCES, [0, 0, 1, 1]))
@pytest.mark.parametrize("running_value", [True, False])
@pytest.mark.parametrize("running_octave", [True, False])
@pytest.mark.parametrize("running_time_sig", [True, False])
def test_roundtrip_cof_notelike_tokenisation(path_resource, track, running_value, running_octave, running_time_sig):
    tokeniser = CoFNotelikeTokeniser(running_value=running_value, running_octave=running_octave,
                                     running_time_sig=running_time_sig)

    _test_roundtrip_tokenisation(tokeniser, path_resource, track)


@pytest.mark.parametrize("path_resource, track", zip(RESOURCES, [0, 0, 1, 1]))
@pytest.mark.parametrize("running_time_sig", [True, False])
def test_roundtrip_large_dictionary_notelike_tokenisation(path_resource, track, running_time_sig):
    tokeniser = LargeDictionaryNotelikeTokeniser(running_time_sig=running_time_sig)

    _test_roundtrip_tokenisation(tokeniser, path_resource, track, quantise=True)


@pytest.mark.parametrize("path_resource, track", zip(RESOURCES, [0, 0, 1, 1]))
def test_roundtrip_midilike_tokenisation(path_resource, track):
    tokeniser = MidilikeTokeniser(running_time_sig=True)

    _test_roundtrip_tokenisation(tokeniser, path_resource, track)


@pytest.mark.parametrize("path_resource, track", zip(RESOURCES, [0, 0, 1, 1]))
def test_roundtrip_gridlike_tokenisation(path_resource, track):
    tokeniser = GridlikeTokeniser(running_time_sig=True)

    _test_roundtrip_tokenisation(tokeniser, path_resource, track)


@pytest.mark.parametrize("path_resource, track", zip(RESOURCES, [0, 0, 1, 1]))
def test_roundtrip_transposed_notelike_tokenisation(path_resource, track):
    tokeniser = TransposedNotelikeTokeniser(running_value=True, running_time_sig=True)

    _test_roundtrip_tokenisation(tokeniser, path_resource, track)


def _test_roundtrip_tokenisation(tokeniser, path_resource, track, quantise=False):
    sequence = Sequence.sequences_load(file_path=path_resource)[track]
    bars = Sequence.sequences_split_bars([sequence], 0)[0]

    if quantise:
        for bar in bars:
            bar.sequence.quantise_and_normalise()

    sequence = Sequence()
    sequence.concatenate([bar.sequence for bar in bars])

    tokens = []

    for i, bar in enumerate(bars):
        tokens.extend(tokeniser.tokenise(bar.sequence))

    sequence_roundtrip = tokeniser.detokenise(tokens)

    assert sequence == sequence_roundtrip

    return tokens
