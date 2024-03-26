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


# @pytest.mark.parametrize("path_resource, track", zip(RESOURCES, [0, 0, 1, 1]))
# @pytest.mark.parametrize("running_value", [True, False])
# @pytest.mark.parametrize("running_pitch", [True, False])
# @pytest.mark.parametrize("running_time_sig", [True, False])
# def test_valid_tokens_notelike_tokenisation(path_resource, track, running_value, running_pitch,
#                                             running_time_sig):
#     tokeniser = NotelikeTokeniser(running_value=running_value, running_pitch=running_pitch,
#                                   running_time_sig=running_time_sig)
#
#     _test_valid_tokens(tokeniser, path_resource, track)


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
            bar.sequence.quantise()
            bar.sequence.cutoff(48, 48)
            bar.sequence.quantise_note_lengths()

    sequence = Sequence()
    sequence.concatenate([bar.sequence for bar in bars])

    tokens = []

    for i, bar in enumerate(bars):
        tokens.extend(tokeniser.tokenise(bar.sequence))

    sequence_roundtrip = tokeniser.detokenise(tokens)

    assert sequence == sequence_roundtrip

    return tokens


def _test_valid_tokens(tokeniser, path_resource, track):
    tokens = _test_roundtrip_tokenisation(tokeniser, path_resource, track)
    tokens.insert(0, 1)
    tokens.append(2)

    valid_tokens, previous_state = tokeniser.get_valid_tokens([])
    assert tokens[0] in valid_tokens

    for i in range(0, len(tokens) - 1):
        valid_tokens, previous_state = tokeniser.get_valid_tokens([tokens[i]], previous_state=previous_state)
        assert tokens[i + 1] in valid_tokens


def test_tokenisation_single():
    quantise = True

    tokeniser = LargeDictionaryNotelikeTokeniser(running_time_sig=True)
    sequence = Sequence.sequences_load(file_path=RESOURCE_CHOPIN)[1]
    bars = Sequence.sequences_split_bars([sequence], meta_track_index=0)[0]

    if quantise:
        for bar in bars:
            bar.sequence.quantise()
            bar.sequence.cutoff(48, 48)
            bar.sequence.quantise_note_lengths()

    sequence = Sequence()
    sequence.concatenate([bar.sequence for bar in bars])

    tokens = []

    for i, bar in enumerate(bars):
        bar_tokens = tokeniser.tokenise(bar.sequence)
        print(bar_tokens)
        tokens.extend(bar_tokens)

    sequence_roundtrip = tokeniser.detokenise(tokens)

    sequence_roundtrip.save("res/out.mid")

    assert sequence == sequence_roundtrip
