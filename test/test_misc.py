import settings.settings
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
