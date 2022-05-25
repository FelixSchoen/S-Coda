from __future__ import annotations

from sCoda.elements.track import Track
from sCoda.sequence.sequence import Sequence


class Composition:
    """ Class representing a composition that contains (multiple) tracks.

    """

    def __init__(self, tracks: [Track]) -> None:
        super().__init__()
        self.tracks = tracks

    def __copy__(self):
        tracks = []

        for track in self.tracks:
            tracks.append(track.__copy__())

        cpy = Composition(tracks)

        return cpy

    @staticmethod
    def from_file(file_path: str, track_indices: [[int]],
                  meta_track_indices: [int], meta_track_index: int = 0) -> Composition:
        """ Creates a new composition from the given MIDI file.

        Args: file_path: Path to the MIDI file track_indices: Array of arrays of track indices, indices in the same
        sub-array will be merged to a single track meta_track_indices: Indices of tracks to consider for meta
        messages meta_track_index: Which final track to merge the meta messages into

        Returns: The created composition

        """
        # Load sequences from file
        merged_sequences = Sequence.sequences_from_midi_file(file_path, track_indices, meta_track_indices,
                                                             meta_track_index)

        # Load composition from sequences
        return Composition.from_sequences(merged_sequences, meta_track_index)

    @staticmethod
    def from_sequences(sequences, meta_track_index: int = 0):
        # Split sequences into bars
        tracks_bars = Sequence.split_into_bars(sequences, meta_track_index=meta_track_index)

        # Create tracks from bars
        tracks = []
        for track_index in range(0, len(tracks_bars)):
            track = Track(tracks_bars[track_index])
            tracks.append(track)

        # Create composition from tracks
        composition = Composition(tracks)
        return composition
