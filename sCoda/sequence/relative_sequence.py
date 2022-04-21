from __future__ import annotations

import copy
import math
import re
import time
from statistics import mean
from typing import TYPE_CHECKING

from sCoda.elements.message import Message, MessageType
from sCoda.sequence.abstract_sequence import AbstractSequence
from sCoda.settings import NOTE_LOWER_BOUND, NOTE_UPPER_BOUND, PPQN, DIFF_DISTANCES_UPPER_BOUND, \
    DIFF_DISTANCES_LOWER_BOUND, DIFF_PATTERN_COVERAGE_UPPER_BOUND, DIFF_PATTERN_COVERAGE_LOWER_BOUND, \
    PATTERN_LENGTH, REGEX_PATTERN, REGEX_SUBPATTERN, DIFF_NOTE_CLASSES_UPPER_BOUND, DIFF_NOTE_CLASSES_LOWER_BOUND, \
    DIFF_NOTE_AMOUNT_UPPER_BOUND, DIFF_NOTE_AMOUNT_LOWER_BOUND
from sCoda.util.logging import get_logger
from sCoda.util.midi_wrapper import MidiTrack, MidiMessage
from sCoda.util.music_theory import KeyNoteMapping, Note, Key
from sCoda.util.util import minmax, simple_regression

if TYPE_CHECKING:
    from sCoda.sequence.absolute_sequence import AbsoluteSequence


class RelativeSequence(AbstractSequence):
    """ Class representing a sequence with relative message timings.

    """

    def __init__(self) -> None:
        super().__init__()

    def __copy__(self):
        copied_messages = []

        for message in self.messages:
            copied_messages.append(message.__copy__())

        copied_sequence = RelativeSequence()
        copied_sequence.messages = copied_messages

        return copied_sequence

    def add_message(self, msg: Message) -> None:
        self.messages.append(msg)

    def adjust_wait_messages(self) -> None:
        """ Consolidates and then splits up wait messages to a maximum size of `PPQN`.

        """
        logger = get_logger(__name__)

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
                    messages_normalized.append(Message(message_type=MessageType.wait, time=int(wait_buffer)))

                # Keep track of open notes
                if msg.message_type == MessageType.note_on:
                    open_messages[msg.note] = True
                elif msg.message_type == MessageType.note_off:
                    open_messages.pop(msg.note, None)

                messages_buffer.append(msg)
                wait_buffer = 0

        # Sanity check
        assert not (wait_buffer > 0 and len(messages_buffer) > 0)

        # Repeat procedure for wait messages that occur at the end of the sequence
        while wait_buffer > PPQN:
            messages_normalized.append(Message(message_type=MessageType.wait, time=PPQN))
            wait_buffer -= PPQN
        if wait_buffer > 0:
            messages_normalized.append(Message(message_type=MessageType.wait, time=int(wait_buffer)))

        # Add messages that are not followed by a wait message
        if len(messages_buffer) > 0:
            messages_normalized.extend(messages_buffer)

        if len(open_messages) > 0:
            logger.info("The sequence contains messages that have not been closed.")

        self.messages = messages_normalized

    def consolidate(self, sequence: RelativeSequence) -> None:
        """ Consolidates the two sequences, resulting in the current sequence containing messages from both of the
        previous sequences.

        Args:
            sequence: A sequence which should be appended to this sequence

        """
        self.messages.extend(sequence.messages)

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

        # If bar is empty, return easiest difficulty
        if len(distances) == 0:
            return 0

        high_distances_mean = mean(sorted(distances, reverse=True)[0: max(1, math.ceil((len(distances) * 0.15)))])

        scaled_difficulty = simple_regression(DIFF_DISTANCES_UPPER_BOUND, 1, DIFF_DISTANCES_LOWER_BOUND, 0,
                                              high_distances_mean)

        return minmax(0, 1, scaled_difficulty)

    def diff_key(self, key: Key = None) -> float:
        """ Calculates the difficulty of the sequence based on the key it is in.

        Here, a key that is further from C is considered more difficult to play, since the performer has to consider
        more accidentals. Furthermore, if no key is specified, a key is guessed based on the amount of the induced
        accidentals that would have to be played.

        Args:
            key: A fixed key of the sequence, will prevent the program from trying to determine one.

        Returns: A value from 0 (low difficulty) to 1 (high difficulty)

        """
        logger = get_logger(__name__)

        key_signature = key

        for msg in self.messages:
            if msg.message_type == MessageType.key_signature:
                if key_signature is not None and key_signature is not msg.key:
                    logger.info(f"Key was {key_signature}, now is {msg.key}.")
                    key_signature = None
                    break
                key_signature = msg.key
            if msg.message_type == MessageType.wait:
                break

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

        scaled_difficulty = simple_regression(7, 1, 0, 0, accidentals)
        return minmax(0, 1, scaled_difficulty)

    def diff_note_amount(self) -> float:
        """ Calculates difficulty of the sequence based on the amount of notes played.

        Returns: A value from 0 (low difficulty) to 1 (high difficulty)

        """
        amount_notes_played = 0

        if self.sequence_length_relation() == 0:
            return 0

        for msg in self.messages:
            if msg.message_type == MessageType.note_on:
                amount_notes_played += 1

        relation = amount_notes_played / self.sequence_length_relation()

        scaled_difficulty = simple_regression(DIFF_NOTE_AMOUNT_UPPER_BOUND, 1, DIFF_NOTE_AMOUNT_LOWER_BOUND, 0,
                                              relation)

        return minmax(0, 1, scaled_difficulty)

    def diff_note_classes(self) -> float:
        """ Calculates difficulty of the sequence based on the amount of note classes (different notes played) in
        relation to the overall amount of messages.

        Returns: A value from 0 (low difficulty) to 1 (high difficulty)

        """
        note_classes = []

        for msg in self.messages:
            if msg.message_type == MessageType.note_on and msg.note not in note_classes:
                note_classes.append(msg.note)

        # If sequence is empty, return easiest difficulty
        if len(note_classes) == 0:
            return 0

        relation = len(note_classes) / self.sequence_length_relation()
        scaled_relation = simple_regression(DIFF_NOTE_CLASSES_UPPER_BOUND, 1, DIFF_NOTE_CLASSES_LOWER_BOUND, 0,
                                            relation)

        return minmax(0, 1, scaled_relation)

    def diff_pattern(self) -> float:
        """ Calculates the difficulty of the sequence based on the patterns of the start messages.

        If a sequence contains patterns, i.e., if a building block is reused several times, the sequence is easier to
        play, since the player has to read fewer notes.

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

        # Obtain patterns, switch to greedy method if pattern matching takes too long
        try:
            results = RelativeSequence._match_pattern(string_representation, start_time=time.time(), max_duration=60)
        except TimeoutError:
            results = RelativeSequence._greedy_match_pattern(string_representation)

        results_with_coverage = []

        # Determine coverage and length of found pattern
        for result in results:
            uncovered = string_representation
            length = 0
            for match in result:
                uncovered = uncovered.replace(match, "")
                length += match.count("+") + match.count("-")
            coverage = (len(string_representation) - len(uncovered)) / len(string_representation)
            results_with_coverage.append((coverage, length, result))

        # Determine best fitting result
        if len(results_with_coverage) > 0:
            best_fit = max(results_with_coverage, key=lambda x: x[0] / x[1])

            bound_difficulty = simple_regression(DIFF_PATTERN_COVERAGE_UPPER_BOUND, 1,
                                                 DIFF_PATTERN_COVERAGE_LOWER_BOUND, 0,
                                                 best_fit[0] / best_fit[1])

            return minmax(0, 1, bound_difficulty)
        else:
            return 1

    def pad_sequence(self, padding_length):
        """ Pads the sequence to a minimum fixed length.

        Args:
            padding_length: The minimum length this sequence should have after this operation

        """
        current_length = 0

        for msg in self.messages:
            if msg.message_type == MessageType.wait:
                current_length += msg.time

                if current_length >= padding_length:
                    break

        if current_length < padding_length:
            self.messages.append(Message(message_type=MessageType.wait, time=padding_length - current_length))

    def sequence_length_relation(self) -> float:
        """ Calculates the length of the sequence in multiples of the `PPQN`.

        Returns: The length of the sequence as a multiple of the `PPQN`

        """
        length = 0

        for msg in self.messages:
            if msg.message_type == MessageType.wait:
                length += msg.time

        return length / PPQN

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

                        if len(current_sequence.messages) > 0:
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

        absolute_sequence.add_message(Message(message_type=MessageType.internal, time=current_point_in_time))

        return absolute_sequence

    def to_midi_track(self) -> MidiTrack:
        """ Converts the sequence to a `MidiTrack`

        Returns: The corresponding `MidiTrack`

        """
        track = MidiTrack()

        for msg in self.messages:
            track.messages.append(MidiMessage.parse_internal_message(msg))

        return track

    def transpose(self, transpose_by: int) -> bool:
        """ Transposes the sequence by the given amount.

        If the lower or upper bound is undercut over exceeded, these notes are transposed by an octave each.

        Args:
            transpose_by: Half-tone steps to transpose by

        Returns: `True` if at least one note had to be shifted due to it otherwise being out of bounds

        """
        had_to_shift = False

        for msg in self.messages:
            if msg.message_type == MessageType.note_on or msg.message_type == MessageType.note_off:
                msg.note += transpose_by
                while msg.note < NOTE_LOWER_BOUND:
                    had_to_shift = True
                    msg.note += 12
                while msg.note > NOTE_UPPER_BOUND:
                    had_to_shift = True
                    msg.note -= 12

        return had_to_shift

    @staticmethod
    def _match_pattern(current_representation, start_time, max_duration=10) -> [[str]]:
        """ Finds all possible combinations of patterns for input string.

        Recursively finds patterns that fit the input ```current_representation```, removes these patterns from the
        input and tries to match the resulting string. Returns all possible combinations of such matches.

        Args:
            current_representation: The current string to pattern-match

        Returns: A list of lists, containing the valid patterns that can be matched, in this order, to the input string

        """
        if time.time() - start_time > max_duration:
            raise TimeoutError

            # Store matches found in this iteration
        local_matches = []
        current_pattern_length = PATTERN_LENGTH

        # Increase length of pattern each step
        while True:
            matches = re.findall(REGEX_PATTERN.format(p_len=current_pattern_length), current_representation)

            # If no more matches, end calculation
            if len(matches) == 0:
                break

            for match in matches:
                matched_string = match[0]

                # Check if match either already handled, or not a valid pattern (since it contains pattern itself)
                if matched_string not in local_matches and re.match(REGEX_SUBPATTERN, matched_string) is None:
                    local_matches.append(matched_string)

            current_pattern_length += 1

        results = []

        # Handle found matches: Remove pattern from input and try to find patterns in the resulting string
        for local_match in local_matches:
            modified_string = current_representation.replace(local_match, "")

            recursive_results = RelativeSequence._match_pattern(modified_string, start_time, max_duration=max_duration)

            # Consider also only parent match
            if local_match not in results:
                results.append([local_match])

            # Add current results to recursive results
            for recursive_result in recursive_results:
                result = [local_match]
                result.extend(recursive_result)
                results.append(result)

        return results

    @staticmethod
    def _greedy_match_pattern(current_representation):
        """ Finds possible combinations of patterns for input string, fixing patterns greedily.

        Only considers the first found pattern for further matching, reducing the time needed to pattern match greatly.

        Args:
            current_representation: The current string to pattern-match

        Returns: A list of lists, containing the valid patterns that can be matched, in this order, to the input string

        """
        # Store matches found in this iteration
        local_match = None
        current_pattern_length = PATTERN_LENGTH

        # Increase length of pattern each step
        while True:
            matches = re.findall(REGEX_PATTERN.format(p_len=current_pattern_length), current_representation)
            match = matches[0] if len(matches) > 0 else None

            # If no more matches, end calculation
            if match is None:
                break

            matched_string = match[0]

            # Check if match either already handled, or not a valid pattern (since it contains pattern itself)
            if re.match(REGEX_SUBPATTERN, matched_string) is None:
                local_match = matched_string

            current_pattern_length += 1

        results = []

        # Handle found matches: Remove pattern from input and try to find patterns in the resulting string
        if local_match is not None:
            modified_string = current_representation.replace(local_match, "")

            recursive_results = RelativeSequence._greedy_match_pattern(modified_string)

            # Consider also only parent match
            if local_match not in results:
                results.append([local_match])

            # Add current results to recursive results
            for recursive_result in recursive_results:
                result = [local_match]
                result.extend(recursive_result)
                results.append(result)

        return results
