from __future__ import annotations

import copy
import logging
import math
import re
from statistics import mean
from typing import TYPE_CHECKING

from sCoda.elements.message import Message, MessageType
from sCoda.sequence.abstract_sequence import AbstractSequence
from sCoda.settings import NOTE_LOWER_BOUND, NOTE_UPPER_BOUND, PPQN, DIFF_DISTANCES_UPPER_BOUND, \
    DIFF_DISTANCES_LOWER_BOUND, SCALE_X3, REGEX_PATTERN, REGEX_SUBPATTERN, PATTERN_LENGTH
from sCoda.util.midi_wrapper import MidiTrack, MidiMessage
from sCoda.util.music_theory import KeyNoteMapping, Note
from sCoda.util.util import minmax, simple_regression, regress

if TYPE_CHECKING:
    from sCoda.sequence.absolute_sequence import AbsoluteSequence


class RelativeSequence(AbstractSequence):
    """ Class representing a sequence with relative message timings.

    """

    def __init__(self) -> None:
        super().__init__()

    def add_message(self, msg: Message) -> None:
        self.messages.append(msg)

    def adjust_wait_messages(self) -> None:
        """ Consolidates and then splits up wait messages to a maximum size of `PPQN`.

        """
        open_messages = dict()
        messages_normalized = []
        messages_buffer = []
        wait_buffer = 0

        for msg in self.messages:
            if msg.message_type == MessageType.wait:
                if len(messages_buffer) > 0:
                    messages_normalized.extend(messages_buffer)
                    messages_buffer = []
                wait_buffer += msg.time
            else:
                # Split up wait messages to maximum length of PPQN
                while wait_buffer > PPQN:
                    messages_normalized.append(Message(message_type=MessageType.wait, time=PPQN))
                    wait_buffer -= PPQN
                if wait_buffer > 0:
                    messages_normalized.append(Message(message_type=MessageType.wait, time=wait_buffer))

                # Keep track of open notes
                if msg.message_type == MessageType.note_on:
                    open_messages[msg.note] = True
                elif msg.message_type == MessageType.note_off:
                    open_messages.pop(msg.note, None)

                messages_buffer.append(msg)
                wait_buffer = 0

        if len(messages_buffer) > 0:
            messages_normalized.extend(messages_buffer)

        if len(open_messages) > 0:
            logging.warning("The sequence contains messages that have not been closed")
        self.messages = messages_normalized

    def consolidate(self, sequence: RelativeSequence) -> None:
        """ Consolidates the two sequences, resulting in the current sequence containing messages from both of the
        previous sequences.

        Args:
            sequence: A sequence which should be appended to this sequence

        """
        self.messages.extend(sequence.messages)

    def diff_key(self) -> float:
        """ Calculates the difficulty of the sequence based on the key it is in.

        Here, a key that is further from C is considered more difficult to play, since the performer has to consider
        more accidentals. Furthermore, if no key is specified, a key is guessed based on the amount of the induced
        accidentals that would have to be played.

        Returns: A value from 0 (low difficulty) to 1 (high difficulty)

        """
        key_signature = None

        for msg in self.messages:
            if msg.message_type == MessageType.key_signature:
                if key_signature is not None:
                    logging.warning("More than one key specified, disregarding information")
                    key_signature = None
                    break
                key_signature = msg.key

        # Have to guess key signature based on induced accidentals
        if key_signature is None:
            key_candidates = []
            for _ in KeyNoteMapping:
                key_candidates.append(0)

            for msg in self.messages:
                if msg.message_type == MessageType.note_on:
                    for i, (_, key_notes) in enumerate(KeyNoteMapping.items()):
                        if Note(msg.note % 12) not in key_notes[0]:
                            key_candidates[i] += 1

            best_index = 0
            best_solution = math.inf
            best_solution_accidentals = math.inf
            key_note_mapping = list(KeyNoteMapping.items())

            for i in range(0, len(key_candidates)):
                if key_candidates[i] <= best_solution:
                    if key_candidates[i] < best_solution or key_note_mapping[i][1][1] < best_solution_accidentals:
                        best_index = i
                        best_solution = key_candidates[i]
                        best_solution_accidentals = key_note_mapping[i][1][1]

            guessed_key = [key for key in KeyNoteMapping][best_index]
            key_signature = guessed_key

        # Check how many accidentals this key uses
        _, accidentals = KeyNoteMapping[key_signature]

        bound_difficulty = minmax(0, 1, simple_regression(7, 1, 0, 0, accidentals))
        return bound_difficulty

    def diff_distances(self) -> float:
        """ Calculates the difficulty of the sequence based on the distances between notes.

        Here, only the top 15% of distances are considered, in order not to disregard notes due to dilution.

        Returns: A value from 0 (low difficulty) to 1 (high difficulty)

        """
        notes_played = []
        current_notes = []
        distances = []

        for msg in self.messages:
            if msg.message_type == MessageType.wait and len(current_notes) > 0:
                notes_played.append(sorted(current_notes))
                current_notes = []
            elif msg.message_type == MessageType.note_on:
                current_notes.append(msg.note)

        for i in range(1, len(notes_played)):
            distance_lower = abs(notes_played[i][0] - notes_played[i - 1][0])
            distance_higher = abs(notes_played[i][-1] - notes_played[i - 1][-1])
            distance = max(distance_lower, distance_higher)
            distances.append(distance)

        high_distances_mean = mean(sorted(distances, reverse=True)[0: max(1, math.ceil((len(distances) * 0.15)))])

        unscaled_difficulty = minmax(0, 1,
                                     simple_regression(DIFF_DISTANCES_UPPER_BOUND, 1, DIFF_DISTANCES_LOWER_BOUND, 0,
                                                       high_distances_mean))
        scaled_mean = regress(unscaled_difficulty, SCALE_X3)

        return minmax(0, 1, scaled_mean)

    def diff_pattern(self) -> float:
        """ Calculates the difficulty of the sequence based on the patterns of the start messages.

        If a sequence contains patterns, i.e., if a building block is reused several times, the sequence is easier to
        play, since the player has to read less notes.

        Returns: A value from 0 (low difficulty) to 1 (high difficulty)

        """
        notes_played = []
        current_bin = []

        for msg in self.messages:
            if msg.message_type == MessageType.wait and len(current_bin) > 0:
                notes_played.extend(sorted(current_bin, key=lambda message: message.note))
            elif msg.message_type == MessageType.note_on:
                notes_played.append(msg)

        string_representation = ""

        # Create string representation
        for i in range(1, len(notes_played)):
            value = notes_played[i].note - notes_played[i - 1].note
            if value >= 0:
                string_representation += "+"
            else:
                string_representation += "-"

            string_representation += str(abs(value))

        regex_pattern = r"(?P<pattern>(?:[+-]\d+)"
        regex_buffer = r"(?:[+-]\d+)*"
        # Regex to match patterns
        regex = regex_pattern + r"{{{p_len}}})" + regex_buffer + r"(?:(?P=pattern)" + regex_buffer + r"){{{p_occ}}}"
        # Check if pattern can be subdivided into smaller pattern
        regex_subpattern = r"^" + regex_pattern + r"+)(?P=pattern)+$"

        current_representation = copy.copy(string_representation)

        result_matches = []

        all_results = RelativeSequence._match_pattern(current_representation)
        print(all_results)

    @staticmethod
    def _match_pattern(current_representation) -> [str]:
        local_matches = []
        current_pattern_length = PATTERN_LENGTH

        while True:
            matches = re.findall(REGEX_PATTERN.format(p_len=current_pattern_length), current_representation)

            # If no more matches, end calculation
            if len(matches) == 0:
                break

            for match in matches:
                matched_string = match[0]

                if matched_string not in local_matches and re.match(REGEX_SUBPATTERN, matched_string) is None:
                    local_matches.append(matched_string)

            current_pattern_length += 1

        print(f"Iteration with string {current_representation}, Local: {local_matches}")

        results = []

        for i, local_match in enumerate(local_matches):
            modified_string = current_representation.replace(local_match, "")

            recursive_results = RelativeSequence._match_pattern(modified_string)

            if len(recursive_results) == 0:
                results.append([local_match])
            else:
                for recursive_result in recursive_results:
                    result = [local_match]
                    result.extend(recursive_result)
                    results.append(result)

        return results



    def split(self, capacities: [int]) -> [RelativeSequence]:
        """ Splits the sequence into parts of the given capacity.

        Creates up to `len(capacities) + 1` new `RelativeSequence`s, where the first `len(capacities)` entries contain
        sequences of the given capacities, while the last one contains any remaining notes. Messages at the boundaries
        of a capacity are split up and possible reinserted at the beginning of the next sequence.

        Args:
            capacities: An array of capacities to split the sequence into

        Returns: An array of `RelativeSequence`s of the desired size

        """
        split_sequences = []
        working_memory = copy.copy(self.messages)

        current_sequence = RelativeSequence()
        open_messages = dict()

        # Try to split current sequence at given point
        for capacity in capacities:
            next_sequence = RelativeSequence()
            next_sequence_queue = []
            remaining_capacity = capacity

            while remaining_capacity >= 0:
                # Check if end-of-sequence was reached prematurely
                if len(working_memory) == 0:
                    if len(current_sequence.messages) > 0:
                        split_sequences.append(current_sequence)
                        current_sequence = next_sequence
                    break

                # Retrieve next message
                msg = working_memory.pop(0)

                # Check messages, if capacity 0 add to next sequence for most of them
                if msg.message_type == MessageType.note_on:
                    if remaining_capacity > 0:
                        current_sequence.add_message(msg)
                        open_messages[msg.note] = copy.copy(msg)
                    else:
                        next_sequence_queue.append(msg)
                # For stop messages, add them to the current sequence
                elif msg.message_type == MessageType.note_off:
                    current_sequence.add_message(msg)
                    open_messages.pop(msg.note, None)
                elif msg.message_type == MessageType.wait:
                    # Can add message in entirety
                    if msg.time <= remaining_capacity:
                        remaining_capacity -= msg.time
                        current_sequence.add_message(msg)
                    # Have to split message
                    else:
                        carry_time = msg.time - remaining_capacity

                        if remaining_capacity > 0:
                            current_sequence.add_message(
                                Message(message_type=MessageType.wait, time=remaining_capacity))

                        for key, value in open_messages.items():
                            current_sequence.add_message(Message(message_type=MessageType.note_off, note=value.note))
                            next_sequence_queue.append(
                                Message(message_type=MessageType.note_on, note=value.note, velocity=value.velocity))

                        next_sequence_queue.append(Message(message_type=MessageType.wait, time=carry_time))

                        split_sequences.append(current_sequence)
                        working_memory[0:0] = next_sequence_queue
                        current_sequence = next_sequence
                        break
                else:
                    if remaining_capacity > 0:
                        current_sequence.add_message(msg)
                    else:
                        next_sequence_queue.append(msg)

        # Check if still capacity left
        if len(working_memory) > 0:
            current_sequence.messages.extend(working_memory)

        # Add current sequence if it is not empty
        if len(current_sequence.messages) > 0:
            split_sequences.append(current_sequence)

        return split_sequences

    def to_absolute_sequence(self) -> AbsoluteSequence:
        """ Converts this `RelativeSequence` to an `AbsoluteSequence`

        Returns: The absolute representation of this sequence

        """
        from sCoda.sequence.absolute_sequence import AbsoluteSequence
        absolute_sequence = AbsoluteSequence()
        current_point_in_time = 0

        for msg in self.messages:
            if msg.message_type == MessageType.wait:
                current_point_in_time += msg.time
            else:
                message_to_add = copy.copy(msg)
                message_to_add.time = current_point_in_time
                absolute_sequence.add_message(message_to_add)

        return absolute_sequence

    def to_midi_track(self) -> MidiTrack:
        """ Converts the sequence to a `MidiTrack`

        Returns: The corresponding `MidiTrack`

        """
        track = MidiTrack()

        for msg in self.messages:
            track.messages.append(MidiMessage.parse_internal_message(msg))

        return track

    def transpose(self, transpose_by: int) -> None:
        """ Transposes the sequence by the given amount.

        If the lower or upper bound is undercut over exceeded, these notes are transposed by an octave each.

        Args:
            transpose_by: Half-tone steps to transpose by

        """
        for msg in self.messages:
            if msg.message_type == MessageType.note_on or msg.message_type == MessageType.note_off:
                msg.note += transpose_by
                while msg.note < NOTE_LOWER_BOUND:
                    msg.note += 12
                while msg.note > NOTE_UPPER_BOUND:
                    msg.note -= 12
