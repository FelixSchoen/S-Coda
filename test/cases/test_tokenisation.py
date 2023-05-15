from base import *
from scoda.utils.tokenisation import MIDIlikeTokeniser


@pytest.mark.parametrize("path_resource, track", zip(RESOURCES, [0, 0, 1, 1]))
def test_roundtrip_notelike_absolute_tokenisation(path_resource, track):
    tokeniser = NotelikeTokeniser(running_value=True, running_time_sig=True)

    sequence = Sequence.from_midi_file(file_path=path_resource)[track]
    bars = Sequence.split_into_bars([sequence], 0)[0]
    sequence = Sequence()
    sequence.concatenate([bar.sequence for bar in bars])

    tokens = []

    for i, bar in enumerate(bars):
        tokens.extend(tokeniser.tokenise(bar.sequence))

    sequence_roundtrip = tokeniser.detokenise(tokens)

    assert sequence == sequence_roundtrip


def test_roundtrip_midilike_absolute_tokenisation():
    tokeniser = MIDIlikeTokeniser(running_value=True, running_time_sig=True)

    sequence = Sequence.from_midi_file(file_path=RESOURCE_SWEEP)[0]
    bars = Sequence.split_into_bars([sequence], 0)[0]
    sequence = Sequence()
    sequence.concatenate([bar.sequence for bar in bars])

    tokens = []

    for i, bar in enumerate(bars):
        tokens.extend(tokeniser.tokenise(bar.sequence))

    sequence_roundtrip = tokeniser.detokenise(tokens)
    sequence_roundtrip.save(str(Path(__file__).parent.parent.joinpath("out").joinpath("deto.mid")))

    assert sequence == sequence_roundtrip
