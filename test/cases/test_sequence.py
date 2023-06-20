from base import *


def test_difficulty_assessment():
    bars = util_split_into_bars()
    bar = bars[0][0]
    for msg in bar.sequence.rel.messages:
        if msg.message_type == MessageType.KEY_SIGNATURE:
            bar.sequence.rel.messages.remove(msg)
            bar.sequence._abs_stale = True
    bar.KEY_SIGNATURE = None

    difficulty = bar.difficulty()

    assert 0 <= difficulty <= 1


def test_midi_to_sequences():
    sequences = util_midi_to_sequences(RESOURCE_BEETHOVEN)

    assert len(sequences) == 2


def test_sequence_from_file_without_parameters():
    sequences = Sequence.from_midi_file(file_path=RESOURCE_BEETHOVEN)

    assert sequences is not None
    for sequence in sequences[:2]:
        assert len(sequence.rel.messages) > 0


def test_piano_rolls():
    sequences = util_midi_to_sequences()
    bars = Sequence.split_into_bars(sequences)

    plot_object = Sequence.pianorolls([bars[0][0].sequence, bars[1][0].sequence])

    assert plot_object is not None


# TODO Delete
# def test_sequence_to_external_representation():
#     sequences = util_midi_to_sequences()
#     sequence = sequences[0]
#     sequence.quantise()
#
#     df_1 = sequence.get_representation(NoteRepresentationType.ABSOLUTE_VALUES,
#                                        TemporalRepresentationType.RELATIVE_TICKS)
#
#     df_2 = sequence.get_representation(NoteRepresentationType.RELATIVE_DISTANCES,
#                                        TemporalRepresentationType.RELATIVE_TICKS)
#
#     df_3 = sequence.get_representation(NoteRepresentationType.CIRCLE_OF_FIFTHS,
#                                        TemporalRepresentationType.RELATIVE_TICKS)
#
#     df_4 = sequence.get_representation(NoteRepresentationType.ABSOLUTE_VALUES,
#                                        TemporalRepresentationType.NOTELIKE_REPRESENTATION)
#
#     df_5 = sequence.get_representation(NoteRepresentationType.RELATIVE_DISTANCES,
#                                        TemporalRepresentationType.NOTELIKE_REPRESENTATION)
#
#     df_6 = sequence.get_representation(NoteRepresentationType.CIRCLE_OF_FIFTHS,
#                                        TemporalRepresentationType.NOTELIKE_REPRESENTATION)
#
#     for data_frame in [df_1, df_2, df_3, df_4, df_5, df_6]:
#         assert data_frame is not None


def test_to_dataframe_is_deprecated():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]
    sequence.to_relative_dataframe()
