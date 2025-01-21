from base import *
from scoda.tokenisation.notelike_tokeniser import MultiTrackLargeVocabularyNotelikeTokeniser


@pytest.mark.parametrize("path_resource", RESOURCES)
def test_roundtrip_multi_track_large_vocabulary_notelike_tokeniser(path_resource):
    tokeniser = MultiTrackLargeVocabularyNotelikeTokeniser(num_instruments=3)

    tokens, sequence_original, sequence_roundtrip = _test_roundtrip_multi_track_tokenisation(tokeniser, path_resource, quantise=True)

    info = tokeniser.get_info(tokens)

    for key, value in info.items():
        assert len(value) == len(tokens)

def _test_roundtrip_multi_track_tokenisation(tokeniser, path_resource, quantise=True, detokenise=True):
    sequences = Sequence.sequences_load(file_path=path_resource)

    for sequence in sequences:
        if quantise:
            sequence.quantise_and_normalise()

    sequences_bars = Sequence.sequences_split_bars(sequences, 0)

    if quantise:
        for sequence_bars in sequences_bars:
            for bar in sequence_bars:
                bar.sequence.quantise_and_normalise()

    sequences_original = []
    for sequence_bars in sequences_bars:
        sequence = Sequence()
        sequence.concatenate([bar.sequence for bar in sequence_bars])
        sequences_original.append(sequence)
    sequence_original = Sequence()
    sequence_original.merge(sequences_original)

    tokens_bars = []

    for i, bars in enumerate(zip(*sequences_bars)):
        bar_tokens = tokeniser.tokenise([bar.sequence for bar in bars])
        tokens_bars.append(bar_tokens)

    tokens = []

    for single_bar_tokens in tokens_bars:
        tokens.extend(single_bar_tokens)

    for token in tokens:
        assert token in tokeniser.dictionary

    if not detokenise:
        return

    encoded = tokeniser.encode(tokens)
    decoded = tokeniser.decode(encoded)

    assert decoded == tokens

    sequences_roundtrip = tokeniser.detokenise(decoded)
    sequence_roundtrip = Sequence()
    sequence_roundtrip.merge(sequences_roundtrip)

    if quantise:
        sequence_roundtrip.quantise_and_normalise()

    assert sequence_original == sequence_roundtrip

    return tokens, sequence_original, sequence_roundtrip
