from __future__ import annotations

import logging

from mido import MidiFile

from sCoda.elements.message import Message
from sCoda.sequence.absolute_sequence import AbsoluteSequence


class Composition:
    """
    Class representing a composition that contains (multiple) tracks.
    """

    def __init__(self) -> None:
        super().__init__()
        self._tracks = []

    @staticmethod
    def from_file(file_path: str, lead_track_index: int, accompanying_track_indices: [int],
                  meta_track_indices: [int]) -> Composition:
        composition = Composition()
        midi_file = MidiFile(file_path)

        # Create absolute sequences
        lead_sequence = AbsoluteSequence()
        acmp_sequences = [AbsoluteSequence() for _ in accompanying_track_indices]

        # Iterate over all tracks in midi file
        for i, track in enumerate(midi_file.tracks):
            # Keep track of current point in time
            current_point_in_time = 0

            # Get current sequence
            current_sequence = None
            if i == lead_track_index:
                current_sequence = lead_sequence
            elif i in accompanying_track_indices:
                current_sequence = acmp_sequences[accompanying_track_indices.index(i)]

            for j, msg in enumerate(track):
                # Add time induced by message
                if msg.time is not None:
                    current_point_in_time += msg.time

                if msg.type == "note_on":
                    current_sequence.add_message(
                        Message.gen_time_signature(msg.numerator, msg.denominator, current_point_in_time))
                elif msg.type == "time_signature":
                    if i not in meta_track_indices:
                        logging.warning("Encountered time signature change in unexpected track")

                    lead_sequence.add_message(
                        Message.gen_time_signature(msg.numerator, msg.denominator, current_point_in_time))

        print()
        for msg in lead_sequence._messages:
            print(msg[1])

        return composition
