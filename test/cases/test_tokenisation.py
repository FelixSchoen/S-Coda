from base import *
from scoda.tokenisation.notelike_tokenisation import MultiTrackLargeVocabularyNotelikeTokeniser


@pytest.mark.parametrize("path_resource", [RESOURCE_MULTI_TRACK])
def test_roundtrip_multi_track_large_vocabulary_notelike_tokeniser(path_resource):
    tokeniser = MultiTrackLargeVocabularyNotelikeTokeniser(num_instruments=4)

    tokens, sequences_original, sequences_roundtrip = _test_roundtrip_multi_track_tokenisation(tokeniser, path_resource,
                                                                                               quantise=True)

    info = tokeniser.get_info(tokens)

    for key, value in info.items():
        assert len(value) == len(tokens)


def _test_roundtrip_multi_track_tokenisation(tokeniser, path_resource, quantise=True, detokenise=True):
    debug = True

    # Load sequences
    sequences = Sequence.sequences_load(file_path=path_resource)

    # Construct step sizes
    default_step_sizes = get_default_step_sizes()
    default_note_values = get_default_note_values()

    # Quantise sequences
    if quantise:
        for sequence in sequences:
            sequence.quantise_and_normalise(step_sizes=default_step_sizes, note_values=default_note_values)

    # Split sequence into bars and quantise again
    sequences_bars = Sequence.sequences_split_bars(sequences, 0)
    if quantise:
        for sequence_bars in sequences_bars:
            for bar in sequence_bars:
                bar.sequence.quantise_and_normalise(step_sizes=default_step_sizes, note_values=default_note_values)

    # Construct original sequence from bars
    sequences_original = []
    for i, sequence_bars in enumerate(sequences_bars):
        sequence = Sequence()
        bars = []

        for j, bar in enumerate(sequence_bars):
            bars.append(bar.sequence)

        sequence.concatenate(bars)
        sequences_original.append(sequence)

    # Store original sequence
    if debug:
        for i, sequence_original in enumerate(sequences_original):
            sequence_original.save(f"out/sequence_original_{i}.mid")

    # Tokenise bars
    tokens_bars = []
    for i, bars in enumerate(zip(*sequences_bars)):
        bar_tokens = tokeniser.tokenise([bar.sequence for bar in bars])
        tokens_bars.append(bar_tokens)
    tokens = []
    for single_bar_tokens in tokens_bars:
        tokens.extend(single_bar_tokens)

    # Sanity check
    for token in tokens:
        assert token in tokeniser.dictionary

    # Preemptive return
    if not detokenise:
        return

    # Encode and decode tokens
    encoded = tokeniser.encode(tokens)
    decoded = tokeniser.decode(encoded)

    # Sanity check
    assert decoded == tokens

    # Detokenise sequence
    sequences_roundtrip = tokeniser.detokenise(decoded)

    if debug:
        # Store roundtrip sequence
        for i, sequence_roundtrip in enumerate(sequences_roundtrip):
            sequence_roundtrip.save(f"out/sequence_roundtrip_{i}.mid")

        # Check equivalence per bar
        roundtrip_bars = Sequence.sequences_split_bars(sequences_roundtrip, 0)
        for c, (channel_original, channel_roundtrip) in enumerate(zip(sequences_bars, roundtrip_bars)):
            for b, (bar_original, bar_roundtrip) in enumerate(zip(channel_original, channel_roundtrip)):
                assert bar_original.sequence.equivalent(bar_roundtrip.sequence, ignore_channel=True,
                                                        ignore_velocity=True)

    # Check equivalence of output sequence
    for sequence_original, sequence_roundtrip in zip(sequences_original, sequences_roundtrip):
        assert sequence_original.equivalent(sequence_roundtrip, ignore_channel=True, ignore_velocity=True)

    return tokens, sequences_original, sequences_roundtrip
