from __future__ import annotations

from mido import MidiFile


class Composition:
    """
    Class representing a composition that contains (multiple) tracks.
    """

    def __init__(self) -> None:
        super().__init__()
        self._tracks = []

    @staticmethod
    def from_file(file_path: str, lead_track_index: int, accompanying_track_indices: [int], meta_track_indices: [int]) -> Composition:
        composition = Composition()
        midi_file = MidiFile(file_path)

        for i, track in enumerate(midi_file.tracks):
            print(i)
            print(track.name)
            if i == 0:
                for msg in track:
                    print(msg)

        return composition
