from base import *


@pytest.mark.parametrize("path_resource, track", zip(RESOURCES, [0, 0, 1, 1]))
def test_roundtrip_notelike_tokenisation(path_resource, track):
    tokeniser = NotelikeTokeniser(running_value=True, running_time_sig=True)

    _test_roundtrip_tokenisation(tokeniser, path_resource, track)


@pytest.mark.parametrize("path_resource, track", zip(RESOURCES, [0, 0, 1, 1]))
def test_roundtrip_midilike_tokenisation(path_resource, track):
    tokeniser = MIDIlikeTokeniser(running_time_sig=True)

    _test_roundtrip_tokenisation(tokeniser, path_resource, track)


@pytest.mark.parametrize("path_resource, track", zip(RESOURCES, [0, 0, 1, 1]))
def test_roundtrip_gridlike_tokenisation(path_resource, track):
    tokeniser = GridlikeTokeniser(running_time_sig=True)

    _test_roundtrip_tokenisation(tokeniser, path_resource, track)


@pytest.mark.parametrize("path_resource, track", zip(RESOURCES, [0, 0, 1, 1]))
def test_roundtrip_transposed_notelike_tokenisation(path_resource, track):
    tokeniser = TransposedNotelikeTokeniser(running_value=True, running_time_sig=True)

    _test_roundtrip_tokenisation(tokeniser, path_resource, track)


def _test_roundtrip_tokenisation(tokeniser, path_resource, track):
    sequence = Sequence.sequences_load(file_path=path_resource)[track]
    bars = Sequence.sequences_split_bars([sequence], 0)[0]
    sequence = Sequence()
    sequence.concatenate([bar.sequence for bar in bars])

    tokens = []

    for i, bar in enumerate(bars):
        tokens.extend(tokeniser.tokenise(bar.sequence))

    sequence_roundtrip = tokeniser.detokenise(tokens)

    assert sequence == sequence_roundtrip


# def test_tokenisation_single():
#     tokeniser = NotelikeTokeniser(running_value=True, running_time_sig=True)
#     sequence = Sequence.from_midi_file(file_path=RESOURCE_SWEEP)[0]
#     bars = Sequence.split_into_bars([sequence], 0)[0]
#     sequence = Sequence()
#     sequence.concatenate([bar.sequence for bar in bars])
#
#     tokens = []
#
#     for i, bar in enumerate(bars):
#         bar_tokens = tokeniser.tokenise(bar.sequence)
#         print(bar_tokens)
#         tokens.extend(bar_tokens)
#
#     sequence_roundtrip = tokeniser.detokenise(tokens)
#
#     sequence_roundtrip.save("res/out.mid")
#
#     assert sequence == sequence_roundtrip
