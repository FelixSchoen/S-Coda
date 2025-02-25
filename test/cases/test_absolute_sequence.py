from base import *
from scoda.enumerations.message_type import MessageType


def test_cutoff():
    sequence = Sequence.sequences_load(file_path=RESOURCE_CHOPIN, track_indices=[[0]], meta_track_indices=[0])[0]
    sequence.cutoff(48, 24)

    for note_pair in sequence.abs.get_message_time_pairings():
        assert note_pair[1].time - note_pair[0].time <= 48


def test_equivalence():
    sequence_a = util_midi_to_sequences()[0]
    sequence_b = util_midi_to_sequences(file=RESOURCE_CHOPIN)[0]

    assert sequence_a == sequence_a
    assert sequence_a != sequence_b


def test_get_message_time_pairings():
    sequence = util_midi_to_sequences()[0]
    note_array = sequence.abs.get_message_time_pairings()

    for i in range(len(note_array) - 1):
        assert note_array[i][0].time <= note_array[i + 1][0].time

        if note_array[i][0].note is not None and note_array[i + 1][0].note is not None:
            assert note_array[i][0].note == note_array[i][1].note
            if note_array[i][0].time == note_array[i + 1][0].time:
                assert note_array[i][0].note <= note_array[i + 1][0].note


def test_get_timing_of_message_type():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    timings = sequence.get_message_times_of_type([MessageType.TIME_SIGNATURE])
    points_in_time = [timing[0] - timings[i - 1][0] if i >= 1 else timing[0] for i, timing in enumerate(timings)]

    split_sequences = sequence.split(points_in_time)

    assert all(len(seq.get_message_times_of_type([MessageType.TIME_SIGNATURE])) <= 1 for seq in split_sequences)


def test_merge():
    sequences = util_midi_to_sequences()
    sequence = Sequence()

    sequence.merge(sequences)

    assert len(sequence.abs.messages) == len(sequences[0].abs.messages) + len(
        sequences[1].abs.messages)
    assert sequence.get_sequence_duration() == max([seq.get_sequence_duration() for seq in sequences])


def test_quantise():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    sequence.quantise([PPQN])

    assert all(msg.time % PPQN == 0 for msg in sequence.abs.messages)


def test_quantise_note_lengths():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    sequence.quantise_and_normalise()

    normal_durations = get_note_durations(NOTE_VALUE_UPPER_BOUND, NOTE_VALUE_LOWER_BOUND)
    triplet_durations = []
    for valid_tuplet in VALID_TUPLETS:
        triplet_durations.extend(get_tuplet_durations(normal_durations, valid_tuplet[0], valid_tuplet[1]))
    dotted_durations = get_dotted_note_durations(normal_durations, DOTTED_ITERATIONS)
    possible_durations = normal_durations + triplet_durations + dotted_durations

    for note_pair in sequence.abs.get_message_time_pairings():
        assert note_pair[1].time - note_pair[0].time in possible_durations


def test_sort():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    sequence.abs.sort()

    assert all(msg.time <= sequence.abs.messages[i + 1].time for i, msg in enumerate(sequence.abs.messages[:-1]))


def test_sequence_duration():
    sequences = util_midi_to_sequences()

    for sequence in sequences:
        sequence_duration = 0
        for msg in sequence.rel.messages:
            if msg.message_type == MessageType.WAIT:
                sequence_duration += msg.time

        assert sequence.get_sequence_duration() == sequence_duration
