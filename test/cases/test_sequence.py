from s_coda.sequence.sequence import NoteRepresentationType, TemporalRepresentationType
from util import *


def test_midi_to_sequences():
    sequences = util_midi_to_sequences(RESOURCE_BEETHOVEN)

    assert len(sequences) == 2


def test_sequence_from_file_without_parameters():
    sequences = Sequence.from_midi_file(RESOURCE_BEETHOVEN)

    assert sequences is not None
    for sequence in sequences[:2]:
        assert len(sequence.rel.messages) > 0


def test_piano_rolls():
    sequences = util_midi_to_sequences()
    bars = Sequence.split_into_bars(sequences)

    plot_object = Sequence.pianorolls([bars[0][0].sequence, bars[1][0].sequence])

    assert plot_object is not None


def test_sequence_to_external_representation():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]
    sequence.quantise()

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

    for data_frame in [df_1, df_2, df_3, df_4, df_5, df_6]:
        assert data_frame is not None
