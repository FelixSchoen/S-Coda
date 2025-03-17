from base import *
from scoda.enumerations.message_type import MessageType


def test_concatenate():
    sequences = util_midi_to_sequences()
    sequence_0 = sequences[0]
    sequence_1 = sequences[1]

    duration_0 = sequence_0.get_sequence_duration()
    duration_1 = sequence_1.get_sequence_duration()

    sequence = Sequence()
    sequence.concatenate([sequence_0, sequence_1])
    duration_post = sequence.get_sequence_duration()

    assert duration_0 + duration_1 == duration_post
    relative_messages = list(sequence.messages_rel())
    assert all(msg in relative_messages for msg in sequence_0.messages_rel())
    assert all(msg in relative_messages for msg in sequence_1.messages_rel())


def test_normalise_relative():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    duration_pre = sequence.get_sequence_duration()

    sequence.normalise()

    duration_post = sequence.get_sequence_duration()

    assert duration_pre == duration_post


def test_pad():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    assert sequence.get_sequence_duration() < PPQN * 4 * 300

    sequence.pad(PPQN * 4 * 300)

    assert sequence.get_sequence_duration() >= PPQN * 4 * 300


def test_split():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]
    original_duration = sequence.get_sequence_duration()

    sequences_split = sequence.split([4 * PPQN])

    assert sequences_split[0].get_sequence_duration() == 4 * PPQN
    assert sequences_split[1].get_sequence_duration() == original_duration - 4 * PPQN


def test_scale():
    sequences = util_midi_to_sequences()

    original_sequence = sequences[0]
    original_bars = Sequence.sequences_split_bars([original_sequence], quantise_note_lengths=False)[0]

    scaled_sequence = copy.copy(original_sequence)
    scale_factor = 0.5
    scaled_sequence.scale(scale_factor)
    scaled_sequence.quantise_and_normalise()

    original_duration = Bar.to_sequence(original_bars).get_sequence_duration()
    scaled_duration = scaled_sequence.get_sequence_duration()

    assert scaled_duration == original_duration * scale_factor


def test_scale_then_create_composition():
    sequences = util_midi_to_sequences()

    assert all(msg.message_type != MessageType.TIME_SIGNATURE for msg in sequences[1].messages_rel())

    compositions = []
    scale_factors = [0.5, 1, 2]

    # Scale sequence by given factors
    for scale_factor in scale_factors:
        scaled_sequences = []

        for i, sequence in enumerate(sequences):
            scaled_sequence = copy.copy(sequence)

            scaled_sequence.quantise_and_normalise()
            scaled_sequence.scale(scale_factor, meta_sequence=sequences[0])

            scaled_sequences.append(scaled_sequence)

            original_time = sequence.get_sequence_duration()
            new_time = scaled_sequence.get_sequence_duration()
            assert np.allclose(original_time*scale_factor, new_time, rtol=0.01)

        # Create composition from scaled sequence
        compositions.append(Composition.from_sequences(scaled_sequences))

    for composition, scale_factor in zip(compositions, scale_factors):
        for i, track in enumerate(composition.tracks):
            original_time = sequences[i].get_sequence_duration()
            new_time = track.to_sequence().get_sequence_duration()
            assert np.allclose(original_time*scale_factor, new_time, rtol=0.01)


def test_transpose():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    note_heights = [msg.note for msg in sequence.messages_rel() if
                    msg.message_type == MessageType.NOTE_ON or msg.message_type == MessageType.NOTE_OFF]

    had_to_wrap = sequence.transpose(1)

    assert not had_to_wrap

    note_heights_after_quantization = [msg.note for msg in sequence.messages_rel() if
                                       msg.message_type == MessageType.NOTE_ON
                                       or msg.message_type == MessageType.NOTE_OFF]

    assert all(
        note_heights_after_quantization[i] == note_heights[i] + 1 for i in range(len(note_heights_after_quantization)))
