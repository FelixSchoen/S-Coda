from base import *
from scoda.midi.midi_file import MidiFile


# Settings

def test_load_settings_from_file():
    load_from_file()


# Util

def test_velocity_values_digitised_to_correct_bins():
    values_to_digitise = [(1, 16), (17, 16), (31, 32), (33, 32), (126, 127)]

    for pair in values_to_digitise:
        assert digitise_velocity(pair[0]) == pair[1]


def test_velocity_digitised_to_correct_bin_indices():
    values_to_digitise = [(1, 0), (17, 0), (31, 1), (33, 1)]

    for pair in values_to_digitise:
        assert bin_velocity(pair[0]) == pair[1]


def test_dotted_note_values():
    values_to_dot = [48, 24, 12]

    assert get_dotted_note_durations(values_to_dot, dotted_iterations=1) == [72, 36, 18]

    assert get_dotted_note_durations(values_to_dot, dotted_iterations=2) == [72, 36, 18, 84, 42, 21]


# MidiFile

def test_midi_file_to_mido_track():
    midi_file = MidiFile.open(RESOURCE_BEETHOVEN)
    mido_track = midi_file.tracks[0].to_mido_track()

    assert isinstance(mido_track, mido.MidiTrack)


# Logging

def test_logging_framework():
    logger = get_logger()
    logger.info("Logging test")

    logger_child = get_logger("test")
    logger_child.info("Child test")


# Example

# def test_example():
#     # Load sequence, choose correct track (often first track contains only meta messages)
#     sequence = Sequence.sequences_load(file_path=RESOURCE_BEETHOVEN)[1]
#
#     # Quantise the sequence to thirty-seconds and thirty-second triplets (standard values)
#     sequence.quantise_and_normalise()
#
#     # Split the sequence into bars based on the occurring time signatures
#     bars = Sequence.sequences_split_bars([sequence], meta_track_index=0)[0]
#
#     # Prepare tokeniser and output tokens
#     tokeniser = StandardNotelikeTokeniser(running_value=True, running_pitch=True, running_time_sig=True)
#     tokens = []
#     difficulties = []
#
#     # Tokenise all bars in the sequence and calculate their difficulties
#     for bar in bars:
#         tokens.extend(tokeniser.tokenise(bar.sequence))
#         difficulties.append(bar.sequence.difficulty())
#
#     # (Conduct ML operations on tokens)
#     tokens = tokens
#
#     # Create sequence from tokens
#     detokenised_sequence = tokeniser.detokenise(tokens)
#
#     # Save sequence
#     Sequence.save = lambda *args: None
#     detokenised_sequence.save("out/generated_sequence.mid")


# Copy

def test_copy_of_elements():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]
    composition = Composition.from_sequences(sequences)

    sequence_copy = copy.copy(sequence)
    composition_copy = copy.copy(composition)

    for msg_orig, msg_copy in zip(sequence.rel._messages, sequence_copy.rel._messages):
        assert msg_orig.message_type == msg_copy.message_type
        assert msg_orig != msg_copy

    for track_orig, track_copy in zip(composition.tracks, composition_copy.tracks):
        for bar_orig, bar_copy in zip(track_orig.bars, track_copy.bars):
            for msg_orig, msg_copy in zip(bar_orig.sequence.rel._messages, bar_copy.sequence.rel._messages):
                assert msg_orig.message_type == msg_copy.message_type
                assert msg_orig != msg_copy
