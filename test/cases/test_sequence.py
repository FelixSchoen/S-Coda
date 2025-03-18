from base import *
from scoda.enumerations.message_type import MessageType


def test_messages_abs():
    sequence = util_midi_to_sequences()[0]
    for _ in sequence.messages_abs():
        pass
    assert sequence._rel_stale is True


def test_messages_rel():
    sequence = util_midi_to_sequences()[0]
    for _ in sequence.messages_rel():
        pass
    assert sequence._abs_stale is True


def test_sequences_load():
    sequences = Sequence.sequences_load(file_path=RESOURCE_BEETHOVEN)

    assert sequences is not None
    for sequence in sequences[:2]:
        assert len(list(sequence.messages_rel())) > 0


def test_plot_pianorolls():
    sequences = util_midi_to_sequences()
    bars = Sequence.sequences_split_bars(sequences)

    plot_object = Sequence.plot_pianorolls([bars[0][0].sequence, bars[1][0].sequence])

    assert plot_object is not None
