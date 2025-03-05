from base import *


def test_copy():
    sequences = util_midi_to_sequences()
    bars = Sequence.sequences_split_bars(sequences)
    bar = bars[0][0]

    bar_copy = copy.copy(bar)

    assert len(bar_copy.sequence.rel._messages) == len(bar.sequence.rel._messages)


def test_to_sequence():
    sequence = util_midi_to_sequences()[0]
    sequence.quantise_and_normalise()

    bars = Sequence.sequences_split_bars([sequence])

    bars_to_consolidate = bars[0]

    consolidated = Bar.to_sequence(bars_to_consolidate)

    time_pre_consolidate = 0
    for bar in bars[0]:
        time_pre_consolidate += bar.sequence.get_sequence_duration()

    time_post_consolidate = consolidated.get_sequence_duration()

    assert time_pre_consolidate == time_post_consolidate
