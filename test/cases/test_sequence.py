from base import *
from scoda.enumerations.message_type import MessageType


def test_difficulty():
    bars = util_split_into_bars()
    bar = bars[0][0]
    for msg in bar.sequence.rel.messages:
        if msg.message_type == MessageType.KEY_SIGNATURE:
            bar.sequence.rel.messages.remove(msg)
            bar.sequence._abs_stale = True
    bar.KEY_SIGNATURE = None

    difficulty = bar.difficulty()

    assert 0 <= difficulty <= 1


def test_sequences_load():
    sequences = Sequence.sequences_load(file_path=RESOURCE_BEETHOVEN)

    assert sequences is not None
    for sequence in sequences[:2]:
        assert len(sequence.rel.messages) > 0


def test_plot_pianorolls():
    sequences = util_midi_to_sequences()
    bars = Sequence.sequences_split_bars(sequences)

    plot_object = Sequence.plot_pianorolls([bars[0][0].sequence, bars[1][0].sequence])

    assert plot_object is not None
