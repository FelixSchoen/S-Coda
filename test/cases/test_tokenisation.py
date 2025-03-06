from base import *
from scoda.tokenisation.notelike_tokenisation import MultiTrackLargeVocabularyNotelikeTokeniser, \
    LargeVocabularyNotelikeTokeniser


@pytest.mark.parametrize("path_resource", [RESOURCE_MULTI_TRACK])
def test_roundtrip_multi_track_large_vocabulary_notelike_tokeniser(path_resource):
    tokeniser = MultiTrackLargeVocabularyNotelikeTokeniser(num_instruments=4)

    tokens, sequence_original, sequence_roundtrip = _test_roundtrip_multi_track_tokenisation(tokeniser, path_resource,
                                                                                             quantise=True)

    info = tokeniser.get_info(tokens)

    for key, value in info.items():
        assert len(value) == len(tokens)


def _test_roundtrip_multi_track_tokenisation(tokeniser, path_resource, quantise=True, detokenise=True):
    debug = False

    sequences = Sequence.sequences_load(file_path=path_resource)

    default_step_sizes = get_default_step_sizes()
    default_note_values = get_default_note_values()

    if quantise:
        for sequence in sequences:
            sequence.quantise_and_normalise(step_sizes=default_step_sizes, note_values=default_note_values)

    sequences_bars = Sequence.sequences_split_bars(sequences, 0)

    if quantise:
        for sequence_bars in sequences_bars:
            for bar in sequence_bars:
                bar.sequence.quantise_and_normalise(step_sizes=default_step_sizes, note_values=default_note_values)

    sequences_original = []
    for i, sequence_bars in enumerate(sequences_bars):
        sequence = Sequence()
        bars = []

        for j, bar in enumerate(sequence_bars):
            bar.sequence.quantise_and_normalise(step_sizes=default_step_sizes, note_values=default_note_values)
            bars.append(bar.sequence)

        sequence.concatenate(bars)
        sequences_original.append(sequence)

    # TODO
    if debug:
        for i, sequence_original in enumerate(sequences_original):
            sequence_original.save(f"out/sequence_original_{i}.mid")

    tokens_bars = []

    for i, bars in enumerate(zip(*sequences_bars)):
        # LOGGER.info(f"Processing bar {i}")
        # for j, bar in enumerate(bars):
        #     bar.sequence.save(f"out/bar_{i}_{j}.mid")
        bar_tokens = tokeniser.tokenise([bar.sequence for bar in bars])
        tokens_bars.append(bar_tokens)
        pass

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

    for i, sequence_roundtrip in enumerate(sequences_roundtrip):
        sequence_roundtrip.save(f"out/sequence_roundtrip_{i}.mid")

    sequence_roundtrip = Sequence()
    sequence_roundtrip.merge(sequences_roundtrip)

    if quantise:
        sequence_roundtrip.quantise_and_normalise(step_sizes=default_step_sizes, note_values=default_note_values)

    assert sequence_original == sequence_roundtrip

    return tokens, sequence_original, sequence_roundtrip


# OLD

@pytest.mark.parametrize("path_resource", RESOURCES)
@pytest.mark.parametrize("running_time_sig", [True, False])
def test_roundtrip_large_vocabulary_notelike_tokenisation(path_resource, running_time_sig):
    tokeniser = LargeVocabularyNotelikeTokeniser(running_time_sig=running_time_sig)

    _test_roundtrip_tokenisation(tokeniser, path_resource, quantise=True)


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

    if quantise:
        sequence_roundtrip.quantise_and_normalise()

    assert sequence == sequence_roundtrip

    return tokens, sequence, sequence_roundtrip, tokens_bars
