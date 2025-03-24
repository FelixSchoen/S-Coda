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
                                             quantise=True,
                                             iteration_identifier=path_resource.stem)


def _test_roundtrip_multi_track_tokenisation(tokeniser, path_resource, merge_sequences, quantise=True, detokenise=True,
                                             iteration_identifier=None):
    debug = True

    # Load sequences
    sequences_original = Sequence.sequences_load(file_path=path_resource)

    # Merge sequences
    if merge_sequences:
        sequence = sequences_original[0]
        sequence.merge(sequences_original[1:])
        sequences_original = [sequence]

    # Construct step sizes
    default_step_sizes = get_default_step_sizes()
    default_note_values = get_default_note_values()

    # Quantise sequences
    if quantise:
        for sequence in sequences_original:
            sequence.quantise_and_normalise(step_sizes=default_step_sizes, note_values=default_note_values)

    # Split sequence into bars and quantise again
    sequences_bars = Sequence.sequences_split_bars(sequences_original, 0)
    if quantise:
        for sequence_bars in sequences_bars:
            for bar in sequence_bars:
                bar.sequence.quantise_and_normalise(step_sizes=default_step_sizes, note_values=default_note_values)

    # Construct original sequence from bars
    sequences_processed = []
    for i, sequence_bars in enumerate(sequences_bars):
        sequence = Sequence()
        bars = []

        for j, bar in enumerate(sequence_bars):
            bars.append(bar.sequence)

        sequence.concatenate(bars)
        sequences_processed.append(sequence)
    bars_original = Sequence.sequences_split_bars(sequences_processed, 0)

    # Store processed sequence
    if debug:
        for i, sequence_processed in enumerate(sequences_processed):
            sequence_processed.save(f"out/{iteration_identifier}_sequence_processed_{i}.mid")

    # Tokenise sequences
    tokens_seqs = tokeniser.tokenise(sequences_processed)

    # Tokenise bars
    tokens_bars = []
    state_dict = dict()
    for i, bars in enumerate(zip(*sequences_bars)):
        bar_tokens = tokeniser.tokenise([bar.sequence for bar in bars], state_dict=state_dict)
        tokens_bars.extend(bar_tokens)

    # Sanity check
    for token in tokens_seqs:
        assert token in tokeniser.dictionary
    for token in tokens_bars:
        assert token in tokeniser.dictionary

    # Preemptive return
    if not detokenise:
        return

    # Encode and decode tokens
    encoded_ps = tokeniser.encode(tokens_seqs)
    decoded_ps = tokeniser.decode(encoded_ps)

    encoded_pb = tokeniser.encode(tokens_bars)
    decoded_pb = tokeniser.decode(encoded_pb)

    # Sanity check
    assert decoded_ps == tokens_seqs
    assert decoded_pb == tokens_bars

    # Detokenise sequence
    sequences_roundtrip_ps = tokeniser.detokenise(decoded_ps)
    sequences_roundtrip_pb = tokeniser.detokenise(decoded_pb)

    if debug:
        # Store roundtrip sequence
        for i, sequence_roundtrip_ps in enumerate(sequences_roundtrip_ps):
            sequence_roundtrip_ps.save(f"out/{iteration_identifier}_sequence_roundtrip_ps_{i}.mid")

        for i, sequence_roundtrip_pb in enumerate(sequences_roundtrip_pb):
            sequence_roundtrip_pb.save(f"out/{iteration_identifier}_sequence_roundtrip_pb_{i}.mid")

    # Check equivalence per bar
    bars_roundtrip_ps = Sequence.sequences_split_bars(sequences_roundtrip_ps, 0)
    for c, (channel_original, channel_roundtrip) in enumerate(zip(bars_original, bars_roundtrip_ps)):
        for b, (bar_original, bar_roundtrip) in enumerate(zip(channel_original, channel_roundtrip)):
            assert bar_original.sequence.equals(bar_roundtrip.sequence, ignore_channel=True, ignore_velocity=True,
                                                ignore_time_signature=True, ignore_key_signature=True)

    bars_roundtrip_pb = Sequence.sequences_split_bars(sequences_roundtrip_pb, 0)
    for c, (channel_original, channel_roundtrip) in enumerate(zip(bars_original, bars_roundtrip_pb)):
        for b, (bar_original, bar_roundtrip) in enumerate(zip(channel_original, channel_roundtrip)):
            assert bar_original.sequence.equals(bar_roundtrip.sequence, ignore_channel=True, ignore_velocity=True,
                                                ignore_time_signature=True, ignore_key_signature=True)

    # Check equivalence of output sequence
    for sequence_processed, sequence_roundtrip_pb in zip(sequences_processed, sequences_roundtrip_pb):
        assert sequence_processed.equals(sequence_roundtrip_pb, ignore_channel=True, ignore_velocity=True,
                                        ignore_time_signature=True, ignore_key_signature=True)

    for sequence_pass_bars, sequence_pass_seqs in zip(sequences_roundtrip_pb, sequences_roundtrip_ps):
        assert sequence_pass_bars.equals(sequence_pass_seqs, ignore_channel=True, ignore_velocity=True,
                                        ignore_time_signature=True, ignore_key_signature=True)

    return tokens_bars, sequences_processed, sequences_roundtrip_pb
