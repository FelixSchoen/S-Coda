from base import *
from scoda.tokenisation.gridlike_tokenisation import GridlikeTokeniser
from scoda.tokenisation.midilike_tokenisation import StandardMidilikeTokeniser, CoFMidilikeTokeniser, \
    RelativeMidilikeTokeniser
from scoda.tokenisation.notelike_tokenisation import CoFNotelikeTokeniser, StandardNotelikeTokeniser, \
    LargeDictionaryNotelikeTokeniser, LargeDictionaryCoFNotelikeTokeniser
from scoda.tokenisation.transposed_notelike_tokenisation import TransposedNotelikeTokeniser


@pytest.mark.parametrize("path_resource", RESOURCES)
@pytest.mark.parametrize("running_time_sig", [True, False])
def test_roundtrip_standard_midilike_tokenisation(path_resource, running_time_sig):
    tokeniser = StandardMidilikeTokeniser(running_time_sig=running_time_sig)

    _test_roundtrip_tokenisation(tokeniser, path_resource)


@pytest.mark.parametrize("path_resource", RESOURCES)
@pytest.mark.parametrize("running_time_sig", [True, False])
def test_roundtrip_relative_midilike_tokenisation(path_resource, running_time_sig):
    tokeniser = RelativeMidilikeTokeniser(running_time_sig=running_time_sig)

    _test_roundtrip_tokenisation(tokeniser, path_resource)


@pytest.mark.parametrize("path_resource", RESOURCES)
@pytest.mark.parametrize("running_octave", [True, False])
@pytest.mark.parametrize("running_time_sig", [True, False])
def test_roundtrip_cof_midilike_tokenisation(path_resource, running_octave, running_time_sig):
    tokeniser = CoFMidilikeTokeniser(running_octave=running_octave, running_time_sig=running_time_sig)

    _test_roundtrip_tokenisation(tokeniser, path_resource)


@pytest.mark.parametrize("path_resource", RESOURCES)
@pytest.mark.parametrize("running_value", [True, False])
@pytest.mark.parametrize("running_pitch", [True, False])
@pytest.mark.parametrize("running_time_sig", [True, False])
def test_roundtrip_standard_notelike_tokenisation(path_resource, running_value, running_pitch,
                                                  running_time_sig):
    tokeniser = StandardNotelikeTokeniser(running_value=running_value, running_pitch=running_pitch,
                                          running_time_sig=running_time_sig)

    _test_roundtrip_tokenisation(tokeniser, path_resource)


@pytest.mark.parametrize("path_resource", RESOURCES)
@pytest.mark.parametrize("running_time_sig", [True, False])
def test_roundtrip_large_dictionary_notelike_tokenisation(path_resource, running_time_sig):
    tokeniser = LargeDictionaryNotelikeTokeniser(running_time_sig=running_time_sig)

    _test_roundtrip_tokenisation(tokeniser, path_resource, quantise=True)


@pytest.mark.parametrize("path_resource", RESOURCES)
@pytest.mark.parametrize("running_value", [True, False])
@pytest.mark.parametrize("running_octave", [True, False])
@pytest.mark.parametrize("running_time_sig", [True, False])
def test_roundtrip_cof_notelike_tokenisation(path_resource, running_value, running_octave, running_time_sig):
    tokeniser = CoFNotelikeTokeniser(running_value=running_value, running_octave=running_octave,
                                     running_time_sig=running_time_sig)

    _test_roundtrip_tokenisation(tokeniser, path_resource)


@pytest.mark.parametrize("path_resource", RESOURCES)
@pytest.mark.parametrize("running_time_sig", [True, False])
def test_roundtrip_large_dictionary_cof_notelike_tokenisation(path_resource, running_time_sig):
    tokeniser = LargeDictionaryCoFNotelikeTokeniser(running_time_sig=running_time_sig)

    _test_roundtrip_tokenisation(tokeniser, path_resource)


@pytest.mark.parametrize("path_resource", RESOURCES)
def test_roundtrip_gridlike_tokenisation(path_resource):
    tokeniser = GridlikeTokeniser(running_time_sig=True)

    _test_roundtrip_tokenisation(tokeniser, path_resource)


@pytest.mark.parametrize("path_resource", RESOURCES)
def test_roundtrip_transposed_notelike_tokenisation(path_resource):
    tokeniser = TransposedNotelikeTokeniser(running_value=True, running_time_sig=True)

    _test_roundtrip_tokenisation(tokeniser, path_resource)


def _test_roundtrip_tokenisation(tokeniser, path_resource, quantise=True, detokenise=True):
    sequences = Sequence.sequences_load(file_path=path_resource)
    sequence = sequences[0]
    sequence.merge(sequences[1:])

    if quantise:
        sequence.quantise_and_normalise()

    bars = Sequence.sequences_split_bars([sequence], 0)[0]

    if quantise:
        for bar in bars:
            bar.sequence.quantise_and_normalise()

    sequence = Sequence()
    sequence.concatenate([bar.sequence for bar in bars])

    tokens = []

    for i, bar in enumerate(bars):
        bar_tokens = tokeniser.tokenise(bar.sequence)
        tokens.extend(bar_tokens)
        break

    if not detokenise:
        return

    sequence_roundtrip = tokeniser.detokenise(tokens)

    assert sequence == sequence_roundtrip

    return tokens, sequence_roundtrip


def _test_constraints(tokeniser, tokens):
    previous_state = None
    valid_tokens = [tokens[0]]

    for i, token in enumerate(tokens):
        assert token in valid_tokens
        valid_tokens, previous_state = tokeniser.get_constraints([tokens[i]], previous_state)


def test_single():
    tokeniser = StandardNotelikeTokeniser(running_value=True, running_pitch=False, running_time_sig=True)

    tokens, sequence_roundtrip = _test_roundtrip_tokenisation(tokeniser, RESOURCE_BEETHOVEN)

    sequence_roundtrip.save("test.mid")
    print(tokens)
    print(sequence_roundtrip.abs.messages)
