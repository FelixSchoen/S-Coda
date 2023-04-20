import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.joinpath("scoda")))

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
from utils.music_theory import *
# noinspection PyUnresolvedReferences
from scoda.utils.util import *
# noinspection PyUnresolvedReferences
import mido

RESOURCES_ROOT = Path(__file__).parent / "resources"
RESOURCE_BEETHOVEN = str(RESOURCES_ROOT / "beethoven_o27-2_m3.mid")
RESOURCE_CHOPIN = str(RESOURCES_ROOT / "chopin_o66_fantaisie_impromptu.mid")


def util_midi_to_sequences(file=None, lead_tracks=None, acmp_tracks=None, meta_tracks=None):
    if file is None:
        file = RESOURCE_BEETHOVEN
    if lead_tracks is None:
        lead_tracks = [1]
    if acmp_tracks is None:
        acmp_tracks = [2]
    if meta_tracks is None:
        meta_tracks = [0, 3]

    midi_file = MidiFile.open_midi_file(file)
    sequences = midi_file.to_sequences([lead_tracks, acmp_tracks], meta_tracks)

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

    composition = Composition.from_midi_file(file, [lead_tracks, acmp_tracks], meta_tracks)

    return composition


def util_split_into_bars(sequences=None):
    if sequences is None:
        sequences = util_midi_to_sequences()

    bars = Sequence.split_into_bars(sequences)

    return bars
