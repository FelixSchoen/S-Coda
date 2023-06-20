from base import *


def test_normalise_relative():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    duration_pre = 0
    for msg in sequence.rel.messages:
        if msg.message_type == MessageType.WAIT:
            duration_pre += msg.time

    sequence.normalise()

    duration_post = 0
    for msg in sequence.rel.messages:
        if msg.message_type == MessageType.WAIT:
            duration_post += msg.time

    assert duration_pre == duration_post


def test_consolidate_sequences():
    sequences = util_midi_to_sequences()
    sequence = Sequence()
    sequence.concatenate([sequences[0], sequences[1]])

    assert all(msg in sequence.rel.messages for msg in sequences[0].rel.messages)
    assert all(msg in sequence.rel.messages for msg in sequences[1].rel.messages)


def test_cutoff():
    sequence = Sequence.sequences_load(file_path=RESOURCE_CHOPIN, track_indices=[[0]], meta_track_indices=[0])[0]
    sequence.cutoff(48, 24)

    for note_pair in sequence.abs.get_message_time_pairings():
        assert note_pair[1].time - note_pair[0].time <= 48


def test_get_valid_next_messages():
    sequences = util_midi_to_sequences()
    bars = Sequence.sequences_split_bars(sequences)
    sequence = bars[0][0].sequence

    assert len(sequence.rel.get_valid_next_messages(2)) == 1


def test_pad_sequence():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    assert sum(
        msg.time for msg in sequence.rel.messages if msg.message_type == MessageType.WAIT) < PPQN * 4 * 300

    sequence.pad(PPQN * 4 * 300)

    assert sum(
        msg.time for msg in sequence.rel.messages if msg.message_type == MessageType.WAIT) >= PPQN * 4 * 300


def test_split():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    split_up = sequence.split([4 * PPQN])

    assert sum(
        msg.time for msg in split_up[0].rel.messages if msg.message_type == MessageType.WAIT) == 4 * PPQN


def test_scale():
    sequences = util_midi_to_sequences()

    original_sequence = sequences[0]
    original_bars = Sequence.sequences_split_bars([original_sequence], quantise_note_lengths=False)[0]

    scaled_sequence = copy.copy(original_sequence)
    scale_factor = 0.5
    scaled_sequence.scale(scale_factor)
    scaled_sequence.quantise()
    scaled_sequence.quantise_note_lengths()

    original_duration = 0
    for bar in original_bars:
        for msg in bar.sequence.rel.messages:
            if msg.message_type == MessageType.WAIT:
                original_duration += msg.time

    scaled_duration = 0
    for msg in scaled_sequence.rel.messages:
        if msg.message_type == MessageType.WAIT:
            scaled_duration += msg.time

    assert scaled_duration == original_duration * scale_factor


def test_scale_then_create_composition():
    sequences = util_midi_to_sequences()

    assert all(msg.message_type != MessageType.TIME_SIGNATURE for msg in sequences[1].rel.messages)

    compositions = []
    scale_factors = [0.5]
    # scale_factors = [0.5, 1, 2]

    # Scale sequence by given factors
    for scale_factor in scale_factors:
        scaled_sequences = []

        for i, sequence in enumerate(sequences):
            scaled_sequence = copy.copy(sequence)

            scaled_sequence.quantise()
            scaled_sequence.quantise_note_lengths()

            scaled_sequence.scale(scale_factor, meta_sequence=sequences[0])

            scaled_sequences.append(scaled_sequence)

            original_time = sequence.abs.messages[-1].time
            new_time = scaled_sequence.abs.messages[-1].time
            assert abs(new_time - original_time * scale_factor) <= 0.01 * new_time

        # Create composition from scaled sequence
        compositions.append(Composition.from_sequences(scaled_sequences))


def test_transpose():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    note_heights = [msg.note for msg in sequence.rel.messages if
                    msg.message_type == MessageType.NOTE_ON or msg.message_type == MessageType.NOTE_OFF]

    had_to_wrap = sequence.transpose(1)

    assert not had_to_wrap

    note_heights_after_quantization = [msg.note for msg in sequence.rel.messages if
                                       msg.message_type == MessageType.NOTE_ON
                                       or msg.message_type == MessageType.NOTE_OFF]

    assert all(
        note_heights_after_quantization[i] == note_heights[i] + 1 for i in range(len(note_heights_after_quantization)))
