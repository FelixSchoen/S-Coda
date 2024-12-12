from lib2to3.btm_utils import tokens

from base import *
from scoda.tokenisation.gridlike_tokenisation import GridlikeTokeniser
from scoda.tokenisation.midilike_tokenisation import StandardMidilikeTokeniser, CoFMidilikeTokeniser, \
    RelativeMidilikeTokeniser
from scoda.tokenisation.notelike_tokenisation import CoFNotelikeTokeniser, StandardNotelikeTokeniser, \
    LargeVocabularyNotelikeTokeniser, LargeVocabularyCoFNotelikeTokeniser, RelativeNotelikeTokeniser
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
def test_roundtrip_large_vocabulary_notelike_tokenisation(path_resource, running_time_sig):
    tokeniser = LargeVocabularyNotelikeTokeniser(running_time_sig=running_time_sig)

    _test_roundtrip_tokenisation(tokeniser, path_resource, quantise=True)


@pytest.mark.parametrize("path_resource", RESOURCES)
@pytest.mark.parametrize("running_value", [True, False])
@pytest.mark.parametrize("running_time_sig", [True, False])
def test_roundtrip_relative_notelike_tokenisation(path_resource, running_value, running_time_sig):
    tokeniser = RelativeNotelikeTokeniser(running_value=running_value, running_time_sig=running_time_sig)

    _test_roundtrip_tokenisation(tokeniser, path_resource)


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
def test_roundtrip_large_vocabulary_cof_notelike_tokenisation(path_resource, running_time_sig):
    tokeniser = LargeVocabularyCoFNotelikeTokeniser(running_time_sig=running_time_sig)

    _test_roundtrip_tokenisation(tokeniser, path_resource)


@pytest.mark.parametrize("path_resource", RESOURCES)
def test_roundtrip_gridlike_tokenisation(path_resource):
    tokeniser = GridlikeTokeniser(running_time_sig=True)

    _test_roundtrip_tokenisation(tokeniser, path_resource)


@pytest.mark.parametrize("path_resource", RESOURCES)
def test_roundtrip_transposed_notelike_tokenisation(path_resource):
    tokeniser = TransposedNotelikeTokeniser(running_value=True, running_time_sig=True)

    _test_roundtrip_tokenisation(tokeniser, path_resource)


@pytest.mark.parametrize("path_resource", RESOURCES)
def test_extras_large_vocabulary_notelike_tokenisation(path_resource):
    tokeniser = LargeVocabularyNotelikeTokeniser(running_time_sig=True)

    tokens, sequence, sequence_roundtrip, tokens_bars = _test_roundtrip_tokenisation(tokeniser, path_resource,
                                                                                     quantise=True, detokenise=True)

    # Mask
    previous_state = None
    for i, single_bar_tokens in enumerate(tokens_bars):
        tokens_with_border_tokens = single_bar_tokens.copy()
        tokens_with_border_tokens.insert(0, 1)
        tokens_with_border_tokens.append(2)
        masks, previous_state = tokeniser.get_mask(tokens_with_border_tokens, previous_state)

        for j, token in enumerate(tokens_with_border_tokens):
            if j == 0:
                continue
            mask = masks[j - 1]
            assert mask[token] != 0

    # Info
    info = tokeniser.get_info(tokens)


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

    tokens_bars = []

    for i, bar in enumerate(bars):
        bar_tokens = tokeniser.tokenise(bar.sequence)
        tokens_bars.append(bar_tokens)

    tokens = []

    for single_bar_tokens in tokens_bars:
        tokens.extend(single_bar_tokens)

    if not detokenise:
        return

    sequence_roundtrip = tokeniser.detokenise(tokens)

    assert sequence == sequence_roundtrip

    return tokens, sequence, sequence_roundtrip, tokens_bars


def _test_constraints(tokeniser, tokens):
    previous_state = None
    valid_tokens = [tokens[0]]

    for i, token in enumerate(tokens):
        assert token in valid_tokens
        valid_tokens, previous_state = tokeniser.get_constraints([tokens[i]], previous_state)

# def test_single():
#     tokeniser = RelativeNotelikeTokeniser(running_value=True, running_time_sig=True)
#
#     tokens, sequence_roundtrip = _test_roundtrip_tokenisation(tokeniser, RESOURCES_ROOT.joinpath("subject.mid"))
#
#     sequence_roundtrip.save("roundtrip.mid")
#     print(tokens)
#     print(sequence_roundtrip.abs.messages)
