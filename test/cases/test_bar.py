from base import *


def test_split_into_bars():
    bars = util_split_into_bars()

    assert len(bars) == 2
    assert len(bars[0]) == len(bars[1])


def test_copy_bar():
    sequences = util_midi_to_sequences()
    bars = Sequence.sequences_split_bars(sequences)
    bar = bars[0][0]

    bar_copy = copy.copy(bar)

    assert len(bar_copy.sequence.rel.messages) == len(bar.sequence.rel.messages)


def test_bars_to_sequence():
    sequence = util_midi_to_sequences()[0]
    sequence.quantise()
    sequence.quantise_note_lengths()

    bars = Sequence.sequences_split_bars([sequence])

    bars_to_consolidate = bars[0]

    consolidated = Bar.to_sequence(bars_to_consolidate)

    time_pre_consolidate = 0
    time_post_consolidate = 0

    for bar in bars[0]:
        for msg in bar.sequence.rel.messages:
            if msg.message_type == MessageType.WAIT:
                time_pre_consolidate += msg.time

    for msg in consolidated.rel.messages:
        if msg.message_type == MessageType.WAIT:
            time_post_consolidate += msg.time

    assert time_pre_consolidate == time_post_consolidate
