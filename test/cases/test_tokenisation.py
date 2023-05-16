from base import *


@pytest.mark.parametrize("path_resource, track", zip(RESOURCES, [0, 0, 1, 1]))
def test_roundtrip_notelike_absolute_tokenisation(path_resource, track):
    tokeniser = NotelikeTokeniser(running_value=True, running_time_sig=True)

    _test_roundtrip_tokenisation(tokeniser, path_resource, track)


@pytest.mark.parametrize("path_resource, track", zip(RESOURCES, [0, 0, 1, 1]))
def test_roundtrip_midilike_absolute_tokenisation(path_resource, track):
    tokeniser = MIDIlikeTokeniser(running_time_sig=True)

    _test_roundtrip_tokenisation(tokeniser, path_resource, track)


@pytest.mark.parametrize("path_resource, track", zip(RESOURCES, [0, 0, 1, 1]))
def test_roundtrip_gridlike_absolute_tokenisation(path_resource, track):
    tokeniser = GridlikeTokeniser(running_time_sig=True)

    _test_roundtrip_tokenisation(tokeniser, path_resource, track)


def _test_roundtrip_tokenisation(tokeniser, path_resource, track):
    sequence = Sequence.from_midi_file(file_path=path_resource)[track]
    bars = Sequence.split_into_bars([sequence], 0)[0]
    sequence = Sequence()
    sequence.concatenate([bar.sequence for bar in bars])

    tokens = []

    for i, bar in enumerate(bars):
        tokens.extend(tokeniser.tokenise(bar.sequence))

    sequence_roundtrip = tokeniser.detokenise(tokens)

    assert sequence == sequence_roundtrip


def test_tokenisation_single():
    tokeniser = GridlikeTokeniser(running_time_sig=True)
    sequence = Sequence.from_midi_file(file_path=RESOURCE_CHOPIN)[1]
    bars = Sequence.split_into_bars([sequence], 0)[0]
    sequence = Sequence()
    sequence.concatenate([bar.sequence for bar in bars])

    tokens = []

    for i, bar in enumerate(bars):
        tokens.extend(tokeniser.tokenise(bar.sequence))

    sequence_roundtrip = tokeniser.detokenise(tokens)

    assert sequence == sequence_roundtrip
