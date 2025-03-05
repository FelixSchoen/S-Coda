from base import *
from scoda.enumerations.message_type import MessageType


def test_cutoff():
    sequence = util_midi_to_sequences()[0]
    sequence.cutoff(48, 24)

    channel_pairings = sequence.get_message_pairings()

    for channel_pairings in channel_pairings.values():
        for message_pairing in channel_pairings:
            assert message_pairing[1].time - message_pairing[0].time <= 48


def test_equivalence():
    sequence_a = util_midi_to_sequences()[0]
    sequence_b = util_midi_to_sequences(file=RESOURCE_CHOPIN)[0]

    assert sequence_a == sequence_a
    assert sequence_a != sequence_b


def test_get_interleaved_message_pairings():
    sequence = util_midi_to_sequences()[0]
    channel_pairings = sequence.get_message_pairings()
    interleaved_pairings = sequence.get_interleaved_message_pairings()

    message_pairings_items = 0
    interleaved_pairings_items = len(interleaved_pairings)

    for message_pairings in channel_pairings.values():
        for _ in message_pairings:
            message_pairings_items += 1

    assert message_pairings_items == interleaved_pairings_items


def test_get_message_time_pairings():
    sequence = util_midi_to_sequences()[0]
    channel_pairings = sequence.get_message_pairings()

    for message_pairings in channel_pairings.values():
        for i in range(len(message_pairings) - 1):
            assert message_pairings[i][0].time <= message_pairings[i + 1][0].time

            if message_pairings[i][0].note is not None and message_pairings[i + 1][0].note is not None:
                assert message_pairings[i][0].note == message_pairings[i][1].note
                if message_pairings[i][0].time == message_pairings[i + 1][0].time:
                    assert message_pairings[i][0].note <= message_pairings[i + 1][0].note


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

    assert len(sequence.abs._messages) == len(sequences[0].abs._messages) + len(
        sequences[1].abs._messages)
    assert sequence.get_sequence_duration() == max([seq.get_sequence_duration() for seq in sequences])


def test_quantise():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    sequence.quantise([PPQN])

    assert all(msg.time % PPQN == 0 for msg in sequence.abs._messages)


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

    channel_pairings = sequence.get_message_pairings()

    for message_pairings in channel_pairings.values():
        for message_pairing in message_pairings:
            assert message_pairing[1].time - message_pairing[0].time in possible_durations


def test_sort():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    sequence.abs.sort()

    assert all(msg.time <= sequence.abs._messages[i + 1].time for i, msg in enumerate(sequence.abs._messages[:-1]))


def test_sequence_duration():
    sequences = util_midi_to_sequences()

    for sequence in sequences:
        sequence_duration = 0
        for msg in sequence.rel._messages:
            if msg.message_type == MessageType.WAIT:
                sequence_duration += msg.time

        assert sequence.get_sequence_duration() == sequence_duration
