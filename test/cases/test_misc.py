from base import *


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
    midi_file = MidiFile.open_midi_file(RESOURCE_BEETHOVEN)
    mido_track = midi_file.tracks[0].to_mido_track()

    assert isinstance(mido_track, mido.MidiTrack)


# Logging

def test_logging_framework():
    logger = get_logger()
    logger.info("Logging test")


# Example

def test_example():
    # Load sequence, choose correct track (often first track contains only meta messages)
    sequence = Sequence.from_midi_file(file_path=RESOURCE_BEETHOVEN)[1]

    # Quantise the sequence to thirty-seconds and thirty-second triplets (standard values)
    sequence.quantise()

    # Split the sequence into bars based on the occurring time signatures
    bars = Sequence.split_into_bars([sequence], meta_track_index=0)[0]

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