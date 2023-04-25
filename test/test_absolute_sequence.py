from base import *


def test_equivalence():
    sequence_a = util_midi_to_sequences()[0]
    sequence_b = util_midi_to_sequences(file=RESOURCE_CHOPIN)[0]

    assert sequence_a == sequence_a
    assert sequence_a != sequence_b


def test_absolute_note_array():
    sequence = util_midi_to_sequences()[0]
    note_array = sequence.abs.absolute_note_array()

    for i in range(len(note_array) - 1):
        assert note_array[i][0].time <= note_array[i + 1][0].time

        if note_array[i][0].note is not None and note_array[i + 1][0].note is not None:
            assert note_array[i][0].note == note_array[i][1].note
            if note_array[i][0].time == note_array[i + 1][0].time:
                assert note_array[i][0].note <= note_array[i + 1][0].note


def test_get_timing_of_message_type():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    timings = sequence.get_message_timing(MessageType.TIME_SIGNATURE)
    points_in_time = [timing[0] - timings[i - 1][0] if i >= 1 else timing[0] for i, timing in enumerate(timings)]

    split_sequences = sequence.split(points_in_time)

    assert all(len(seq.get_message_timing(MessageType.TIME_SIGNATURE)) <= 1 for seq in split_sequences)


def test_merge_sequences():
    sequences = util_midi_to_sequences()
    sequence = Sequence()

    sequence.merge(sequences)

    assert len(sequence.abs.messages) == len(sequences[0].abs.messages) + len(
        sequences[1].abs.messages)


def test_quantise():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    sequence.quantise([PPQN])

    assert all(msg.time % PPQN == 0 for msg in sequence.abs.messages)


def test_quantise_note_lengths():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    sequence.quantise([PPQN])
    sequence.quantise_note_lengths()

    normal_durations = get_note_durations(NOTE_VALUE_UPPER_BOUND, NOTE_VALUE_LOWER_BOUND)
    triplet_durations = []
    for valid_tuplet in VALID_TUPLETS:
        triplet_durations.extend(get_tuplet_durations(normal_durations, valid_tuplet[0], valid_tuplet[1]))
    dotted_durations = get_dotted_note_durations(normal_durations, DOTTED_ITERATIONS)
    possible_durations = normal_durations + triplet_durations + dotted_durations

    for note_pair in sequence.abs.absolute_note_array():
        assert note_pair[1].time - note_pair[0].time in possible_durations


def test_sequence_length():
    sequences = util_midi_to_sequences()

    assert all(sequence.sequence_length() == sequences[0].sequence_length() for sequence in sequences)
