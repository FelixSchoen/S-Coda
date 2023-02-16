import copy

import mido

from util import *
from fixtures import RESOURCE_BEETHOVEN, RESOURCE_CHOPIN
from s_coda import Sequence, Composition, Bar
from s_coda.elements.message import MessageType
from s_coda.sequence.sequence import NoteRepresentationType, TemporalRepresentationType
from s_coda.settings import PPQN
from s_coda.util.midi_wrapper import MidiFile
from s_coda.util.util import digitise_velocity, bin_from_velocity


# General


# Sequence


def test_pianorolls():
    sequences = util_midi_to_sequences()
    bars = Sequence.split_into_bars(sequences)

    Sequence.pianorolls([bars[0][0].sequence, bars[1][0].sequence])


def test_sequence_from_file_without_parameters():
    sequences = Sequence.from_midi_file(RESOURCE_BEETHOVEN)

    assert sequences is not None


def test_sequence_to_external_representation():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]
    sequence.quantise()

    print()
    df_1 = sequence.to_external_representation(NoteRepresentationType.absolute_values,
                                               TemporalRepresentationType.relative_ticks)

    df_2 = sequence.to_external_representation(NoteRepresentationType.relative_distances,
                                               TemporalRepresentationType.relative_ticks)

    df_3 = sequence.to_external_representation(NoteRepresentationType.circle_of_fifths,
                                               TemporalRepresentationType.relative_ticks)

    df_4 = sequence.to_external_representation(NoteRepresentationType.absolute_values,
                                               TemporalRepresentationType.notelike_representation)

    df_5 = sequence.to_external_representation(NoteRepresentationType.relative_distances,
                                               TemporalRepresentationType.notelike_representation)

    df_6 = sequence.to_external_representation(NoteRepresentationType.circle_of_fifths,
                                               TemporalRepresentationType.notelike_representation)


# Bar

def test_copy_bar():
    sequences = util_midi_to_sequences()
    bars = Sequence.split_into_bars(sequences)
    bar = bars[0][0]

    bar_copy = copy.copy(bar)

    assert len(bar_copy.sequence.rel.messages) == len(bar.sequence.rel.messages)


def test_bars_to_sequence():
    sequence = util_midi_to_sequences()[0]
    sequence.quantise()
    sequence.quantise_note_lengths()

    bars = Sequence.split_into_bars([sequence])

    bars_to_consolidate = bars[0]

    consolidated = Bar.to_sequence(bars_to_consolidate)

    time_pre_consolidate = 0
    time_post_consolidate = 0

    for bar in bars[0]:
        for msg in bar.sequence.rel.messages:
            if msg.message_type == MessageType.wait:
                time_pre_consolidate += msg.time

    for msg in consolidated.rel.messages:
        if msg.message_type == MessageType.wait:
            time_post_consolidate += msg.time

    assert time_pre_consolidate == time_post_consolidate


# Track

def test_track_to_sequence():
    composition = util_load_composition()
    track = composition.tracks[0]
    seq = track.to_sequence()

    assert isinstance(seq, Sequence)


# Relative Sequence

def test_adjust_wait_messages():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    duration_pre = 0
    for msg in sequence.rel.messages:
        if msg.message_type == MessageType.wait:
            duration_pre += msg.time

    sequence.adjust_messages()

    duration_post = 0
    for msg in sequence.rel.messages:
        if msg.message_type == MessageType.wait:
            duration_post += msg.time

    assert duration_pre == duration_post
    assert all((not (msg.message_type == MessageType.wait) or msg.time <= PPQN) for msg in sequence.rel.messages)


def test_consolidate_sequences():
    sequences = util_midi_to_sequences()
    sequence = Sequence()
    sequence.concatenate([sequences[0], sequences[1]])

    assert all(msg in sequence.rel.messages for msg in sequences[0].rel.messages)
    assert all(msg in sequence.rel.messages for msg in sequences[1].rel.messages)


def test_cutoff():
    sequence = Sequence.from_midi_file(RESOURCE_CHOPIN, [[0]], [0])[0]
    sequence.cutoff(48, 24)


def test_get_valid_next_messages():
    sequences = util_midi_to_sequences()
    bars = Sequence.split_into_bars(sequences)
    sequence = bars[0][0].sequence

    assert len(sequence.rel.get_valid_next_messages(2)) == 1


def test_difficulty_assessment():
    bars = util_split_into_bars()
    bar = bars[0][0]
    for msg in bar.sequence.rel.messages:
        if msg.message_type == MessageType.key_signature:
            bar.sequence.rel.messages.remove(msg)
            bar.sequence._abs_stale = True
    bar.key_signature = None

    difficulty = bar.difficulty()

    assert 0 <= difficulty <= 1


def test_pad_sequence():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    assert sum(
        msg.time for msg in sequence.rel.messages if msg.message_type == MessageType.wait) < PPQN * 4 * 300

    sequence.pad_sequence(PPQN * 4 * 300)

    assert sum(
        msg.time for msg in sequence.rel.messages if msg.message_type == MessageType.wait) >= PPQN * 4 * 300


def test_split():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    split_up = sequence.split([4 * PPQN])

    assert sum(
        msg.time for msg in split_up[0].rel.messages if msg.message_type == MessageType.wait) == 4 * PPQN


def test_scale():
    sequences = util_midi_to_sequences()

    original_sequence = sequences[0]
    original_bars = Sequence.split_into_bars([original_sequence], quantise_note_lengths=False)[0]

    scaled_sequence = copy.copy(original_sequence)
    scale_factor = 0.5
    scaled_sequence.scale(scale_factor)
    scaled_sequence.quantise()
    scaled_sequence.quantise_note_lengths()

    original_duration = 0
    for bar in original_bars:
        for msg in bar.sequence.rel.messages:
            if msg.message_type == MessageType.wait:
                original_duration += msg.time

    scaled_duration = 0
    for msg in scaled_sequence.rel.messages:
        if msg.message_type == MessageType.wait:
            scaled_duration += msg.time

    assert scaled_duration == original_duration * scale_factor


def test_scale_then_create_composition():
    sequences = util_midi_to_sequences()

    assert all(msg.message_type != MessageType.time_signature for msg in sequences[1].rel.messages)

    compositions = []
    scale_factors = [0.5]

    # Scale sequences by given factors
    for scale_factor in scale_factors:
        scaled_sequences = []

        for i, sequence in enumerate(sequences):
            scaled_sequence = copy.copy(sequence)

            scaled_sequence.quantise()
            scaled_sequence.quantise_note_lengths()

            scaled_sequence.scale(scale_factor, meta_sequence=sequences[0])

            scaled_sequence.quantise()
            scaled_sequence.quantise_note_lengths()

            scaled_sequences.append(scaled_sequence)

        # Create composition from scaled sequences
        compositions.append(Composition.from_sequences(scaled_sequences))


def test_transpose():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    note_heights = [msg.note for msg in sequence.rel.messages if
                    msg.message_type == MessageType.note_on or msg.message_type == MessageType.note_off]

    had_to_wrap = sequence.transpose(1)

    assert not had_to_wrap

    note_heights_after_quantization = [msg.note for msg in sequence.rel.messages if
                                       msg.message_type == MessageType.note_on
                                       or msg.message_type == MessageType.note_off]

    assert all(
        note_heights_after_quantization[i] == note_heights[i] + 1 for i in range(len(note_heights_after_quantization)))


# Absolute Sequence

def test_get_timing_of_message_type():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]

    timings = sequence.get_message_timing(MessageType.time_signature)
    points_in_time = [timing[0] - timings[i - 1][0] if i >= 1 else timing[0] for i, timing in enumerate(timings)]

    split_sequences = sequence.split(points_in_time)

    assert all(len(seq.get_message_timing(MessageType.time_signature)) <= 1 for seq in split_sequences)


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


def test_sequence_length():
    sequences = util_midi_to_sequences()

    assert all(sequence.sequence_length() == sequences[0].sequence_length() for sequence in sequences)


# Util

def test_velocity_values_digitised_to_correct_bins():
    values_to_digitise = [(1, 16), (17, 16), (31, 32), (33, 32), (126, 127)]

    for pair in values_to_digitise:
        assert digitise_velocity(pair[0]) == pair[1]


def test_velocity_digitised_to_correct_bin_indices():
    values_to_digitise = [(1, 0), (17, 0), (31, 1), (33, 1)]

    for pair in values_to_digitise:
        assert bin_from_velocity(pair[0]) == pair[1]


# MidiFile

def test_midi_file_to_mido_track():
    midi_file = MidiFile.open_midi_file(RESOURCE_BEETHOVEN)
    mido_track = midi_file.tracks[0].to_mido_track()

    assert isinstance(mido_track, mido.MidiTrack)


# Mido

def test_print_midi_file():
    midi_file = mido.MidiFile()

    for track in midi_file.tracks:
        print()
        print("new track")
        for msg in track:
            print(msg)

    print(len(midi_file.tracks))


# Utils


