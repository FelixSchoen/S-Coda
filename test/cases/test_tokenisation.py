from base import *
from scoda.tokenisation.notelike_tokenisation import MultiTrackLargeVocabularyNotelikeTokeniser


@pytest.mark.parametrize("path_resource, num_tracks",
                         list(zip(RESOURCES_MULTI_TRACK, RESOURCES_MULTI_TRACK_NUM_TRACKS)))
def test_roundtrip_multi_track_large_vocabulary_notelike_tokeniser(path_resource, num_tracks):
    tokeniser = MultiTrackLargeVocabularyNotelikeTokeniser(num_tracks=num_tracks)

    tokens, sequences_original, sequences_roundtrip = _test_roundtrip_multi_track_tokenisation(tokeniser, path_resource,
                                                                                               merge_sequences=num_tracks == 1,
                                                                                               quantise=True,
                                                                                               iteration_identifier=path_resource.stem)

    info = tokeniser.get_info(tokens)

    for key, value in info.items():
        assert len(value) == len(tokens)


def test_roundtrip_manual_tokeniser():
    path_resource = RESOURCE_BEETHOVEN
    num_tracks = 1
    tokeniser = MultiTrackLargeVocabularyNotelikeTokeniser(num_tracks=num_tracks)
    _test_roundtrip_multi_track_tokenisation(tokeniser, path_resource,
                                             merge_sequences=num_tracks == 1,
                                             quantise=True)


def _test_roundtrip_multi_track_tokenisation(tokeniser, path_resource, merge_sequences, quantise=True, detokenise=True,
                                             iteration_identifier=None):
    debug = True

    # Load sequences
    sequences = Sequence.sequences_load(file_path=path_resource)

    # Merge sequences
    if merge_sequences:
        sequence = sequences[0]
        sequence.merge(sequences[1:])
        sequences = [sequence]

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
    bars_original = Sequence.sequences_split_bars(sequences_original, 0)

    # Store original sequence
    if debug:
        for i, sequence_original in enumerate(sequences_original):
            sequence_original.save(f"out/{iteration_identifier}_sequence_original_{i}.mid")

    # Tokenise bars
    tokens_bars = []
    state_dict = dict()
    for i, bars in enumerate(zip(*sequences_bars)):
        bar_tokens = tokeniser.tokenise([bar.sequence for bar in bars], state_dict=state_dict)
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
            sequence_roundtrip.save(f"out/{iteration_identifier}_sequence_roundtrip_{i}.mid")

    # Check equivalence per bar
    bars_roundtrip = Sequence.sequences_split_bars(sequences_roundtrip, 0)
    for c, (channel_original, channel_roundtrip) in enumerate(zip(bars_original, bars_roundtrip)):
        for b, (bar_original, bar_roundtrip) in enumerate(zip(channel_original, channel_roundtrip)):
            assert bar_original.sequence.equals(bar_roundtrip.sequence, ignore_channel=True, ignore_velocity=True,
                                                ignore_time_signature=True, ignore_key_signature=True)

    # Check equivalence of output sequence
    for sequence_original, sequence_roundtrip in zip(sequences_original, sequences_roundtrip):
        assert sequence_original.equals(sequence_roundtrip, ignore_channel=True, ignore_velocity=True,
                                        ignore_time_signature=True, ignore_key_signature=True)

    return tokens, sequences_original, sequences_roundtrip
