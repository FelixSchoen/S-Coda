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
        assert bin_from_velocity(pair[0]) == pair[1]


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

def test_example():
    # Load sequence, choose correct track (often first track contains only meta messages)
    sequence = Sequence.sequences_load(file_path=RESOURCE_BEETHOVEN)[1]

    # Quantise the sequence to thirty-seconds and thirty-second triplets (standard values)
    sequence.quantise()

    # Split the sequence into bars based on the occurring time signatures
    bars = Sequence.sequences_split_bars([sequence], meta_track_index=0)[0]

    # Prepare tokeniser and output tokens
    tokeniser = NotelikeTokeniser(running_value=True, running_time_sig=True)
    tokens = []
    difficulties = []

    # Tokenise all bars in the sequence and calculate their difficulties
    for bar in bars:
        tokens.extend(tokeniser.tokenise(bar.sequence))
        difficulties.append(bar.sequence.difficulty())

    # (Conduct ML operations on tokens)
    tokens = tokens

    # Create sequence from tokens
    detokenised_sequence = tokeniser.detokenise(tokens)

    # Save sequence
    Sequence.save = lambda *args: None
    detokenised_sequence.save("out/generated_sequence.mid")


# Copy

def test_copy_of_elements():
    sequences = util_midi_to_sequences()
    sequence = sequences[0]
    composition = Composition.from_sequences(sequences)

    sequence_copy = copy.copy(sequence)
    composition_copy = copy.copy(composition)

    for msg_orig, msg_copy in zip(sequence.rel.messages, sequence_copy.rel.messages):
        assert msg_orig.message_type == msg_copy.message_type
        assert msg_orig != msg_copy

    for track_orig, track_copy in zip(composition.tracks, composition_copy.tracks):
        for bar_orig, bar_copy in zip(track_orig.bars, track_copy.bars):
            for msg_orig, msg_copy in zip(bar_orig.sequence.rel.messages, bar_copy.sequence.rel.messages):
                assert msg_orig.message_type == msg_copy.message_type
                assert msg_orig != msg_copy


# Debug

# def test_midi_messages():
#     midi_file = MidiFile.open_midi_file(Path(__file__).parent.parent.joinpath("res").joinpath("subject.mid"))
#
#     for i, track in enumerate(midi_file.tracks):
#         print(f"Track {i + 1}")
#         for j, message in enumerate(track.messages):
#             print(message)
#
#

def test_subject():
    sequences = Sequence.sequences_load(Path(__file__).parent.parent.joinpath("res").joinpath("subject.mid"))

    compositions = []

    for scale_factor in [1]:
        scaled_sequences = []

        for sequence in sequences:
            scaled_sequence = copy.copy(sequence)

            scaled_sequence.quantise()
            scaled_sequence.quantise_note_lengths()

            # Scale by scale factor, using first track as meta information track
            scaled_sequence.scale(scale_factor, sequences[0])

            scaled_sequences.append(scaled_sequence)

        # Create composition from scaled sequences
        composition = Composition.from_sequences(scaled_sequences)
        compositions.append(composition)

    # Extract bars
    bars = [[track.bars for track in composition.tracks] for composition in compositions]

    def _assign_difficulty(bar: Bar) -> float:
        bar.difficulty()
        assert bar.sequence._difficulty is not None
        return bar.difficulty()

    # Assign difficulties
    if True:
        for bars_composition in bars:
            for bars_track in bars_composition:
                for bar in bars_track:
                    _assign_difficulty(bar)

    bars_augmented = []

    def _augment_transpose(bars: list[list[Bar]], assign_difficulties) -> list[list[list[Bar]]]:
        transposed_segments = []

        for transpose_by in [-5]:
            transposed_tracks = []
            for bars_track in bars:
                transposed_track = []
                for bar in bars_track:
                    transposed_bar = copy.copy(bar)
                    transposed_bar.transpose(transpose_by)
                    if assign_difficulties:
                        transposed_bar.difficulty()
                    transposed_track.append(bar)
                transposed_tracks.append(transposed_track)
            transposed_segments.append(transposed_tracks)

        return transposed_segments

    # Augment by transposing
    if True:
        for bars_composition in bars:
            bars_transposed = _augment_transpose(bars_composition, True)
            bars_augmented.extend(bars_transposed)
