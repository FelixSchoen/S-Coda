import copy

import mido

from sCoda import Sequence, Composition, Bar
from sCoda.elements.message import MessageType, Message
from sCoda.settings import PPQN
from sCoda.util.midi_wrapper import MidiFile
from sCoda.util.music_theory import Key
from sCoda.util.util import digitise_velocity, bin_from_velocity


# General

def test_load_composition():
    composition = Composition.from_file("resources/beethoven_o27-2_m3.mid", [[1], [2]], [0, 3])

    assert len(composition.tracks) == 2

    return composition


def test_midi_to_sequences(file="resources/beethoven_o27-2_m3.mid", lead_tracks=None, acmp_tracks=None,
                           meta_tracks=None):
    if lead_tracks is None:
        lead_tracks = [1]

    if acmp_tracks is None:
        acmp_tracks = [2]

    if meta_tracks is None:
        meta_tracks = [0, 3]

    midi_file = MidiFile.open_midi_file(file)
    sequences = midi_file.to_sequences([lead_tracks, acmp_tracks], meta_tracks)

    assert len(sequences) == 2

    return sequences


# Sequence


def test_split_into_bars():
    sequences = test_midi_to_sequences()
    bars = Sequence.split_into_bars(sequences)

    assert len(bars) == 2
    assert len(bars[0]) == len(bars[1])

    return bars


def test_pianorolls():
    sequences = test_midi_to_sequences()
    bars = Sequence.split_into_bars(sequences)

    Sequence.pianorolls([bars[0][0].sequence, bars[1][0].sequence])


# Bar

def test_copy_bar():
    sequences = test_midi_to_sequences()
    bars = Sequence.split_into_bars(sequences)
    bar = bars[0][0]

    bar_copy = copy.copy(bar)

    assert len(bar_copy.sequence.rel.messages) == len(bar.sequence.rel.messages)


def test_bars_to_sequence():
    sequence = test_midi_to_sequences()[0]
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


# Relative Sequence

def test_adjust_wait_messages():
    sequences = test_midi_to_sequences()
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
    sequences = test_midi_to_sequences()
    sequence = Sequence()
    sequence.consolidate([sequences[0], sequences[1]])

    assert all(msg in sequence.rel.messages for msg in sequences[0].rel.messages)
    assert all(msg in sequence.rel.messages for msg in sequences[1].rel.messages)


def test_get_valid_next_messages():
    sequences = test_midi_to_sequences()
    bars = Sequence.split_into_bars(sequences)
    sequence = bars[0][0].sequence

    assert len(sequence.rel.get_valid_next_messages(2)) == 1


def test_difficulty_assessment():
    bars = test_split_into_bars()
    bar = bars[0][0]
    for msg in bar.sequence.rel.messages:
        if msg.message_type == MessageType.key_signature:
            bar.sequence.rel.messages.remove(msg)
            bar.sequence._abs_stale = True
    bar.key_signature = None

    difficulty = bar.difficulty()

    assert 0 <= difficulty <= 1


def test_pad_sequence():
    sequences = test_midi_to_sequences()
    sequence = sequences[0]

    assert sum(
        msg.time for msg in sequence.rel.messages if msg.message_type == MessageType.wait) < PPQN * 4 * 300

    sequence.pad_sequence(PPQN * 4 * 300)

    assert sum(
        msg.time for msg in sequence.rel.messages if msg.message_type == MessageType.wait) >= PPQN * 4 * 300


def test_split():
    sequences = test_midi_to_sequences()
    sequence = sequences[0]

    split_up = sequence.split([4 * PPQN])

    assert sum(
        msg.time for msg in split_up[0].rel.messages if msg.message_type == MessageType.wait) == 4 * PPQN


def test_scale():
    sequences = test_midi_to_sequences()

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
    sequences = test_midi_to_sequences(file="resources/albeniz_op165_caprichocatalan.mid")

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
    sequences = test_midi_to_sequences()
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
    sequences = test_midi_to_sequences()
    sequence = sequences[0]

    timings = sequence.get_message_timing(MessageType.time_signature)
    points_in_time = [timing[0] - timings[i - 1][0] if i >= 1 else timing[0] for i, timing in enumerate(timings)]

    split_sequences = sequence.split(points_in_time)

    assert all(len(seq.get_message_timing(MessageType.time_signature)) <= 1 for seq in split_sequences)


def test_merge_sequences():
    sequences = test_midi_to_sequences()
    sequence = Sequence()

    sequence.merge(sequences)

    assert len(sequence.abs.messages) == len(sequences[0].abs.messages) + len(
        sequences[1].abs.messages)


def test_quantise():
    sequences = test_midi_to_sequences()
    sequence = sequences[0]

    sequence.quantise([PPQN])

    assert all(msg.time % PPQN == 0 for msg in sequence.abs.messages)


def test_quantise_note_lengths():
    sequences = test_midi_to_sequences()
    sequence = sequences[0]

    sequence.quantise([PPQN])
    sequence.quantise_note_lengths()


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
    midi_file = MidiFile.open_midi_file("resources/beethoven_o27-2_m3.mid")
    mido_track = midi_file.tracks[0].to_mido_track()

    assert isinstance(mido_track, mido.MidiTrack)


# Mido

def test_print_midi_file():
    midi_file = mido.MidiFile("resources/two_bars_split.mid")

    for track in midi_file.tracks:
        for msg in track:
            print(msg)


# Misc

def test_message_representation():
    msg = Message(message_type=MessageType.note_on, note=42, time=10, numerator=4, denominator=4, velocity=127,
                  control=0, key=Key.c)

    representation = msg.__repr__()

    assert "42" in representation
