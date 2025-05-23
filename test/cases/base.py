import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.joinpath("scoda")))

# noinspection PyUnresolvedReferences
import scoda as sc
# noinspection PyUnresolvedReferences
from scoda.elements.bar import *
# noinspection PyUnresolvedReferences
from scoda.elements.composition import *
# noinspection PyUnresolvedReferences
from scoda.sequences.sequence import *
# noinspection PyUnresolvedReferences
from scoda.settings.settings import *
# noinspection PyUnresolvedReferences
from scoda.misc.music_theory import *
# noinspection PyUnresolvedReferences
from scoda.misc.util import *
# noinspection PyUnresolvedReferences
from scoda.misc.scoda_logging import get_logger
# noinspection PyUnresolvedReferences
import mido
# noinspection PyUnresolvedReferences
import pytest

LOGGER = get_logger(__name__)

RESOURCES_ROOT = Path(__file__).parent.parent.joinpath("res")
RESOURCE_BEETHOVEN = RESOURCES_ROOT.joinpath("beethoven_o27-2_m3.mid")
RESOURCE_CHOPIN = RESOURCES_ROOT.joinpath("chopin_o66_fantaisie_impromptu.mid")
RESOURCE_MOZART = RESOURCES_ROOT.joinpath("mozart_331_1.mid")
RESOURCE_RACHMANINOW = RESOURCES_ROOT.joinpath("rachmaninow_op23_5.mid")
RESOURCE_SWEEP = RESOURCES_ROOT.joinpath("sweep.mid")
RESOURCE_EMPTY_BARS = RESOURCES_ROOT.joinpath("empty_bars.mid")
RESOURCE_MULTI_TRACK = RESOURCES_ROOT.joinpath("multi_track.mid")
RESOURCES = [RESOURCE_SWEEP, RESOURCE_EMPTY_BARS,
             RESOURCE_BEETHOVEN, RESOURCE_CHOPIN, RESOURCE_MOZART, RESOURCE_RACHMANINOW]
RESOURCES_MULTI_TRACK = [RESOURCE_MULTI_TRACK] + RESOURCES
RESOURCES_MULTI_TRACK_NUM_TRACKS = [4, 1, 1, 1, 1, 1, 1]


def util_midi_to_sequences(file=None, lead_tracks=None, acmp_tracks=None, meta_tracks=None):
    if file is None:
        file = RESOURCE_BEETHOVEN
    if lead_tracks is None:
        lead_tracks = [1]
    if acmp_tracks is None:
        acmp_tracks = [2]
    if meta_tracks is None:
        meta_tracks = [0, 3]

    midi_file = MidiFile.open(file)
    sequences = midi_file.convert([lead_tracks, acmp_tracks], meta_tracks)

    return sequences


def util_load_composition(file=None, lead_tracks=None, acmp_tracks=None, meta_tracks=None):
    if file is None:
        file = RESOURCE_BEETHOVEN
    if lead_tracks is None:
        lead_tracks = [1]
    if acmp_tracks is None:
        acmp_tracks = [2]
    if meta_tracks is None:
        meta_tracks = [0, 3]

    composition = Composition.from_midi_file(file_path=file, track_indices=[lead_tracks, acmp_tracks],
                                             meta_track_indices=meta_tracks)

    return composition


def util_split_into_bars(sequences=None):
    if sequences is None:
        sequences = util_midi_to_sequences()

    bars = Sequence.sequences_split_bars(sequences)

    return bars
