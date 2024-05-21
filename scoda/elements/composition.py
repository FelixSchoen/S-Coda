from __future__ import annotations

import copy

from scoda.elements.track import Track
from scoda.sequences.sequence import Sequence


class Composition:
    """Class representing a composition that contains (multiple) tracks.
    """

    def __init__(self, tracks: [Track]) -> None:
        super().__init__()
        self.tracks = tracks

    def __copy__(self) -> Composition:
        tracks = [copy.copy(track) for track in self.tracks]

        cpy = Composition(tracks)
        return cpy

    @staticmethod
    def from_midi_file(file_path: str, track_indices: [[int]],
                       meta_track_indices: [int], meta_track_index: int = 0) -> Composition:
        """Creates a new composition from the given MIDI file.

        Args:
            file_path: Path to the MIDI file
            track_indices: Array of arrays of track indices, indices in the same
                sub-array will be merged to a single track
            meta_track_indices: Indices of tracks to consider for meta messages
            meta_track_index: Which final track to merge the meta messages into

        Returns: The created composition
        """
        # Load sequence from file
        merged_sequences = Sequence.sequences_load(file_path=file_path,
                                                   track_indices=track_indices,
                                                   meta_track_indices=meta_track_indices,
                                                   target_meta_track_index=meta_track_index)

        # Quantisation
        for sequence in merged_sequences:
            sequence.quantise_and_normalise()

        # Load composition from sequence
        return Composition.from_sequences(merged_sequences, meta_track_index)

    @staticmethod
    def from_sequences(sequences, meta_track_index: int = 0) -> Composition:
        # Split sequence into bars
        tracks_bars = Sequence.sequences_split_bars(sequences, meta_track_index=meta_track_index)

        # Create tracks from bars
        tracks = []
        for track_index in range(0, len(tracks_bars)):
            track = Track(tracks_bars[track_index])
            tracks.append(track)

        # Create composition from tracks
        composition = Composition(tracks)
        return composition

    def to_sequences(self):
        sequences = []
        for track in self.tracks:
            sequences.append(track.to_sequence())
        return sequences

    def save(self, file_path: str):
        sequences = self.to_sequences()
        Sequence.sequences_save(sequences, file_path)