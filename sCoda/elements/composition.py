from __future__ import annotations

from sCoda.elements.track import Track
from sCoda.sequence.sequence import Sequence
from sCoda.util.midi_wrapper import MidiFile
from sCoda.util.util import get_note_durations, get_tuplet_durations


class Composition:
    """ Class representing a composition that contains (multiple) tracks.

    """

    def __init__(self, tracks: [Track]) -> None:
        super().__init__()
        self._tracks = tracks

    @property
    def tracks(self) -> [Track]:
        return self._tracks

    @staticmethod
    def from_file(file_path: str, track_indices: [[int]],
                  meta_track_indices: [int], meta_track_index: int = 0) -> Composition:
        """ Creates a new composition from the given MIDI file.

        Args: file_path: Path to the MIDI file track_indices: Array of arrays of track indices, indices in the same
        sub-array will be merged to a single track meta_track_indices: Indices of tracks to consider for meta
        messages meta_track_index: Which final track to merge the meta messages into

        Returns: The created composition

        """
        # Open file
        midi_file = MidiFile.open_midi_file(file_path)

        # Get sequences from MIDI file
        merged_sequences = midi_file.to_sequences(track_indices, meta_track_indices,
                                                  meta_track_index=meta_track_index)

        # Construct quantisation parameters
        quantise_parameters = get_note_durations(1, 8)
        quantise_parameters += get_tuplet_durations(quantise_parameters, 3, 2)

        # Quantisation
        for sequence in merged_sequences:
            sequence.quantise(quantise_parameters)
            sequence.quantise_note_lengths()

        # Split sequences into bars
        tracks_bars = Sequence.split_into_bars(merged_sequences, meta_track_index=meta_track_index)

        # Create tracks from bars
        tracks = []
        for track_index in range(0, len(tracks_bars)):
            track = Track(tracks_bars[track_index])
            tracks.append(track)

        # Create composition from tracks
        composition = Composition(tracks)
        return composition
