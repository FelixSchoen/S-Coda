from base import *
from scoda.tokenisation.notelike_tokenisation import MultiTrackLargeVocabularyNotelikeTokeniser


@pytest.mark.parametrize("path_resource, num_tracks",
                         list(zip(RESOURCES_MULTI_TRACK, RESOURCES_MULTI_TRACK_NUM_TRACKS)))
@pytest.mark.parametrize("flag_absolute_bar_position", [True, True])
@pytest.mark.parametrize("flag_fuse_track", [False, True])
def test_roundtrip_multi_track_large_vocabulary_notelike_tokeniser(path_resource, num_tracks,
                                                                   flag_absolute_bar_position, flag_fuse_track, ):
    tokeniser = MultiTrackLargeVocabularyNotelikeTokeniser(num_tracks=num_tracks,
                                                           flag_absolute_bar_position=flag_absolute_bar_position,
                                                           flag_fuse_track=flag_fuse_track,
                                                           bar_position_quarters_range=6)

    tokens, sequences_original, sequences_roundtrip = _test_roundtrip_multi_track_tokenisation(tokeniser, path_resource,
                                                                                               merge_sequences=num_tracks == 1,
                                                                                               quantise=True,
                                                                                               iteration_identifier=path_resource.stem)

    info = tokeniser.get_info(tokens)

    for key, value in info.items():
        assert len(value) == len(tokens)

    for i, i_pos in enumerate(info["info_position"]):
        assert i_pos == i

    last_time = 0
    for i_time in info["info_time"]:
        assert i_time >= last_time
        last_time = i_time


def test_roundtrip_manual_tokeniser():
    path_resource = RESOURCE_MOZART
    num_tracks = 1
    tokeniser = MultiTrackLargeVocabularyNotelikeTokeniser(num_tracks=num_tracks, flag_fuse_track=False,
                                                           flag_absolute_bar_position=True,
                                                           bar_position_quarters_range=6)
    tokens, sequences_original, sequences_roundtrip = _test_roundtrip_multi_track_tokenisation(tokeniser, path_resource,
                                                                                               merge_sequences=num_tracks == 1,
                                                                                               quantise=True,
                                                                                               iteration_identifier=path_resource.stem)

    info = tokeniser.get_info(tokens)

    for key, value in info.items():
        assert len(value) == len(tokens)

    for i, i_pos in enumerate(info["info_position"]):
        assert i_pos == i

    cur_pos_bar = 0
    for i, i_pos in enumerate(info["info_position_bar"]):
        if i_pos == 0:
            cur_pos_bar = 0
        assert i_pos == cur_pos_bar

        cur_pos_bar += 1

    last_time = 0
    for i_time in info["info_time"]:
        assert i_time >= last_time
        last_time = i_time

    last_time_bar = 0
    for i_time in info["info_time_bar"]:
        if i_time == 0:
            last_time_bar = 0

        assert i_time >= last_time_bar
        last_time_bar = i_time


def _test_roundtrip_multi_track_tokenisation(tokeniser, path_resource, merge_sequences, quantise=True, detokenise=True,
                                             iteration_identifier=None):
    debug = False

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


def test_get_hierarchy_transitions_basic():
    """Test basic hierarchy transitions computation with known values."""
    tokeniser = MultiTrackLargeVocabularyNotelikeTokeniser(
        ppqn=24,
        num_tracks=1,
        flag_absolute_bar_position=False,
        flag_fuse_track=True
    )

    # Create a simple token sequence with known timing
    # REST tokens advance time: rst_24 advances by 24 ticks
    # At PPQN=24: one quarter note = 24 ticks
    tokens = [
        "sta",                              # time=0
        "trk_00-pit_060-val_24-vel_127",    # time=0, note at tick 0
        "rst_24",                           # time=24
        "trk_00-pit_062-val_24-vel_127",    # time=24, note at tick 24
        "rst_24",                           # time=48
        "trk_00-pit_064-val_24-vel_127",    # time=48, note at tick 48
        "rst_24",                           # time=72
        "bar",                              # time=96 (bar boundary)
        "trk_00-pit_065-val_24-vel_127",    # time=96, note at tick 96
        "rst_24",                           # time=120
    ]

    # Test with intervals: beats (24 ticks) and bars (96 ticks)
    intervals = [24, 96]
    assignments = tokeniser.get_hierarchy_transitions(tokens, intervals)

    # Verify structure
    assert len(assignments) == 2, "Should have 2 hierarchy levels"
    assert len(assignments[0]) == len(tokens), "Level 0 should have same length as tokens"
    assert len(assignments[1]) == len(tokens), "Level 1 should have same length as tokens"

    # Get timing info for verification
    info = tokeniser.get_info(tokens)
    info_time = info["info_time"]

    # Verify each position's segment ID
    for pos in range(len(tokens)):
        expected_beat_segment = info_time[pos] // 24
        expected_bar_segment = info_time[pos] // 96
        assert assignments[0][pos] == expected_beat_segment, f"Beat segment mismatch at pos {pos}"
        assert assignments[1][pos] == expected_bar_segment, f"Bar segment mismatch at pos {pos}"


def test_get_hierarchy_transitions_padding():
    """Test that padding works correctly."""
    tokeniser = MultiTrackLargeVocabularyNotelikeTokeniser(
        ppqn=24,
        num_tracks=1,
        flag_fuse_track=True
    )

    tokens = [
        "sta",
        "trk_00-pit_060-val_24-vel_127",
        "rst_24",
        "sto"
    ]

    intervals = [24, 96]
    seq_len = 10  # Pad to length 10

    assignments = tokeniser.get_hierarchy_transitions(tokens, intervals, seq_len=seq_len)

    # Verify padded length
    assert len(assignments[0]) == seq_len, "Should be padded to seq_len"
    assert len(assignments[1]) == seq_len, "Should be padded to seq_len"

    # Verify padding value
    for level in range(2):
        for pos in range(len(tokens), seq_len):
            assert assignments[level][pos] == -1, f"Padding position {pos} at level {level} should be -1"


def test_get_hierarchy_transitions_custom_padding_value():
    """Test that custom padding value works."""
    tokeniser = MultiTrackLargeVocabularyNotelikeTokeniser(ppqn=24, num_tracks=1)

    tokens = ["sta", "sto"]
    intervals = [24]
    seq_len = 5
    padding_value = -999

    assignments = tokeniser.get_hierarchy_transitions(
        tokens, intervals, seq_len=seq_len, padding_value=padding_value
    )

    # Verify custom padding value
    for pos in range(len(tokens), seq_len):
        assert assignments[0][pos] == padding_value


def test_get_hierarchy_transitions_three_levels():
    """Test with three hierarchy levels (beats, bars, phrases)."""
    tokeniser = MultiTrackLargeVocabularyNotelikeTokeniser(
        ppqn=24,
        num_tracks=1,
        flag_fuse_track=True
    )

    # Create longer sequence spanning multiple bars
    tokens = ["sta"]
    for i in range(16):  # 16 quarter notes = 4 bars at 4/4
        tokens.append("trk_00-pit_060-val_24-vel_127")
        tokens.append("rst_24")
        if (i + 1) % 4 == 0:  # Bar every 4 beats
            tokens.append("bar")
    tokens.append("sto")

    # Intervals: beat (24), bar (96), 4-bar phrase (384)
    intervals = [24, 96, 384]
    assignments = tokeniser.get_hierarchy_transitions(tokens, intervals)

    # Verify we have 3 levels
    assert len(assignments) == 3

    # Get timing info
    info = tokeniser.get_info(tokens)

    # Verify segment IDs increase monotonically (or stay same)
    for level in range(3):
        prev_segment = -1
        for pos in range(len(tokens)):
            current_segment = assignments[level][pos]
            assert current_segment >= prev_segment, \
                f"Segment IDs should be monotonically increasing at level {level}"
            prev_segment = current_segment


@pytest.mark.parametrize("path_resource", [RESOURCE_MOZART, RESOURCE_BEETHOVEN])
def test_get_hierarchy_transitions_real_music(path_resource):
    """Test hierarchy transitions on real music files."""
    tokeniser = MultiTrackLargeVocabularyNotelikeTokeniser(
        ppqn=24,
        num_tracks=1,
        flag_fuse_track=True,
        flag_absolute_bar_position=False
    )

    # Load and prepare sequence
    sequences = Sequence.sequences_load(file_path=path_resource)
    sequence = sequences[0]
    sequence.merge(sequences[1:])

    default_step_sizes = get_default_step_sizes()
    default_note_values = get_default_note_values()
    sequence.quantise_and_normalise(step_sizes=default_step_sizes, note_values=default_note_values)

    # Tokenise
    tokens = tokeniser.tokenise([sequence])

    # Compute hierarchy assignments
    intervals = [24, 96, 384]  # beats, bars, 4-bar phrases
    assignments = tokeniser.get_hierarchy_transitions(tokens, intervals)

    # Basic validation
    assert len(assignments) == 3
    for level in range(3):
        assert len(assignments[level]) == len(tokens)
        # No padding values (we didn't request padding)
        assert all(v >= 0 for v in assignments[level])

    # Verify coarser levels have fewer unique segments
    unique_level_0 = len(set(assignments[0]))
    unique_level_1 = len(set(assignments[1]))
    unique_level_2 = len(set(assignments[2]))

    assert unique_level_0 >= unique_level_1, "Finer level should have >= unique segments"
    assert unique_level_1 >= unique_level_2, "Finer level should have >= unique segments"
