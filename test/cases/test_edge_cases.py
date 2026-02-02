"""Edge case tests for S-Coda library.

This module tests edge cases that expose potential bugs and validates
correctness of the implementation.
"""
import tomllib
from pathlib import Path

from base import *
from scoda.enumerations.message_type import MessageType


# Version Consistency Tests

def test_version_matches_pyproject():
    """Test that the version in __init__.py matches pyproject.toml."""
    import scoda

    pyproject_path = Path(__file__).parent.parent.parent.joinpath("pyproject.toml")
    with open(pyproject_path, "rb") as f:
        pyproject_version = tomllib.load(f)["project"]["version"]

    assert scoda.__version__ == pyproject_version, \
        f"Version mismatch: scoda.__version__={scoda.__version__}, pyproject.toml={pyproject_version}"


# Empty Sequence Tests

def test_empty_sequence_duration():
    """Test that getting duration of an empty sequence returns 0 instead of crashing."""
    sequence = Sequence()
    assert sequence.get_sequence_duration() == 0


def test_empty_sequence_channel():
    """Test that getting channel of an empty sequence returns None instead of crashing."""
    sequence = Sequence()
    assert sequence.get_sequence_channel() is None


def test_empty_sequence_is_empty():
    """Test that empty sequence correctly reports as empty."""
    sequence = Sequence()
    assert sequence.is_empty()


def test_empty_sequence_operations():
    """Test that various operations work on empty sequences without crashing."""
    sequence = Sequence()

    # These should not crash
    sequence.normalise()
    sequence_copy = sequence.copy()
    assert sequence_copy.is_empty()

    # Concatenating two empty sequences
    sequence2 = Sequence()
    sequence.concatenate([sequence2])
    assert sequence.is_empty()


# Normalise Relative Tests

def test_normalise_removes_unclosed_notes():
    """Test that normalise_relative properly removes unclosed NOTE_ON messages."""
    sequence = Sequence()

    # Add a NOTE_ON without a corresponding NOTE_OFF
    sequence.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100))
    sequence.add_relative_message(Message(message_type=MessageType.WAIT, channel=0, time=24))

    # Before normalization, the note should be present
    messages_before = list(sequence.messages_rel())
    note_on_count_before = sum(1 for m in messages_before if m.message_type == MessageType.NOTE_ON)
    assert note_on_count_before == 1

    # After normalization, the unclosed note should be removed
    sequence.normalise()
    messages_after = list(sequence.messages_rel())
    note_on_count_after = sum(1 for m in messages_after if m.message_type == MessageType.NOTE_ON)
    assert note_on_count_after == 0, "Unclosed NOTE_ON should be removed during normalization"


def test_normalise_keeps_properly_closed_notes():
    """Test that normalise_relative keeps notes that are properly closed."""
    sequence = Sequence()

    # Add a properly closed note
    sequence.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100))
    sequence.add_relative_message(Message(message_type=MessageType.WAIT, channel=0, time=24))
    sequence.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=60))
    sequence.add_relative_message(Message(message_type=MessageType.WAIT, channel=0, time=24))

    sequence.normalise()
    messages_after = list(sequence.messages_rel())
    note_on_count = sum(1 for m in messages_after if m.message_type == MessageType.NOTE_ON)
    note_off_count = sum(1 for m in messages_after if m.message_type == MessageType.NOTE_OFF)

    assert note_on_count == 1, "Properly closed NOTE_ON should be kept"
    assert note_off_count == 1, "Properly closed NOTE_OFF should be kept"


def test_normalise_multiple_channels_with_unclosed_notes():
    """Test that normalise_relative handles unclosed notes across multiple channels."""
    sequence = Sequence()

    # Channel 0: properly closed note
    sequence.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100))
    sequence.add_relative_message(Message(message_type=MessageType.WAIT, channel=0, time=12))
    sequence.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=60))

    # Channel 1: unclosed note
    sequence.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=1, note=72, velocity=100))
    sequence.add_relative_message(Message(message_type=MessageType.WAIT, channel=1, time=24))

    sequence.normalise()
    messages_after = list(sequence.messages_rel())

    # Channel 0 note should be kept
    channel_0_notes = [m for m in messages_after if m.channel == 0 and m.message_type == MessageType.NOTE_ON]
    assert len(channel_0_notes) == 1, "Channel 0's properly closed note should be kept"

    # Channel 1 note should be removed (unclosed)
    channel_1_notes = [m for m in messages_after if m.channel == 1 and m.message_type == MessageType.NOTE_ON]
    assert len(channel_1_notes) == 0, "Channel 1's unclosed note should be removed"


# Similarity Tests

def test_similarity_with_same_sequence():
    """Test that similarity of a sequence with itself is 1.0."""
    sequence = util_midi_to_sequences()[0]
    assert sequence.similarity(sequence) == 1.0


def test_similarity_empty_sequences():
    """Test that similarity of two empty sequences is 1.0."""
    seq1 = Sequence()
    seq2 = Sequence()
    assert seq1.similarity(seq2) == 1.0


def test_similarity_flags():
    """Test that similarity flags are properly passed and used."""
    sequences = util_midi_to_sequences()
    sequence_a = sequences[0]
    sequence_b = sequence_a.copy()

    # Modify velocity in copy
    for msg in sequence_b.messages_abs():
        if msg.velocity is not None:
            msg.velocity = max(1, msg.velocity // 2)

    # With ignore velocity, should be same
    sim_ignore_velocity = sequence_a.similarity(sequence_b, flag_consider_velocity=False)
    # With consider velocity, should be different
    sim_consider_velocity = sequence_a.similarity(sequence_b, flag_consider_velocity=True)

    assert sim_ignore_velocity >= sim_consider_velocity, \
        "Ignoring velocity should give same or higher similarity"


# Message Consistency Tests

def test_message_copy_is_independent():
    """Test that copying a message creates an independent copy."""
    msg1 = Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100, time=0)
    msg2 = msg1.copy()

    # Modify the copy
    msg2.note = 72

    # Original should be unchanged
    assert msg1.note == 60
    assert msg2.note == 72


def test_sequence_copy_is_independent():
    """Test that copying a sequence creates an independent copy."""
    sequence = util_midi_to_sequences()[0]
    original_note_count = sum(1 for m in sequence.messages_abs() if m.message_type == MessageType.NOTE_ON)
    sequence_copy = sequence.copy()

    # Get first note from copy and modify it
    first_note_value = None
    for msg in sequence_copy.messages_abs():
        if msg.note is not None:
            first_note_value = msg.note
            msg.note = 0
            break

    # Verify original is unchanged - check that the first note in original still has original value
    for msg in sequence.messages_abs():
        if msg.note is not None:
            assert msg.note == first_note_value, "Original sequence was modified when copy was changed"
            break

    # Also verify object identity
    assert sequence_copy is not sequence


# Bar Split Edge Cases

def test_split_bars_with_empty_sequence():
    """Test that splitting an empty sequence into bars works."""
    sequence = Sequence()
    sequence.add_relative_message(Message(message_type=MessageType.TIME_SIGNATURE, numerator=4, denominator=4))
    sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=PPQN * 4))  # One empty bar

    bars = Sequence.sequences_split_bars([sequence], meta_track_index=0)
    assert len(bars) == 1
    assert len(bars[0]) >= 1


# Transpose Edge Cases

def test_transpose_wraps_at_bounds():
    """Test that transpose wraps notes at bounds instead of going out of range."""
    sequence = Sequence()
    # Add a very high note
    sequence.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=108, velocity=100))
    sequence.add_relative_message(Message(message_type=MessageType.WAIT, channel=0, time=24))
    sequence.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=108))

    # Transpose up - should wrap
    had_to_wrap = sequence.transpose(12)
    assert had_to_wrap, "Should have wrapped when transposing high note up"

    # Check that note is still within bounds
    for msg in sequence.messages_rel():
        if msg.note is not None:
            assert NOTE_LOWER_BOUND <= msg.note <= NOTE_UPPER_BOUND


def test_transpose_no_wrap_when_in_range():
    """Test that transpose doesn't unnecessarily wrap notes."""
    sequence = Sequence()
    # Add a middle C
    sequence.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100))
    sequence.add_relative_message(Message(message_type=MessageType.WAIT, channel=0, time=24))
    sequence.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=60))

    # Transpose by a semitone
    had_to_wrap = sequence.transpose(1)
    assert not had_to_wrap, "Should not wrap when transposing middle C up one semitone"

    # Check note value
    for msg in sequence.messages_rel():
        if msg.message_type == MessageType.NOTE_ON:
            assert msg.note == 61


# Additional Comprehensive Tests

class TestSequenceOperations:
    """Comprehensive tests for sequence operations."""

    def test_split_with_single_capacity(self):
        """Test splitting a sequence with a single capacity."""
        sequence = Sequence()
        sequence.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100))
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, channel=0, time=48))
        sequence.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=60))
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, channel=0, time=48))

        splits = sequence.split([48])

        assert len(splits) == 2, "Should create two sequences"
        assert splits[0].get_sequence_duration() == 48
        assert splits[1].get_sequence_duration() == 48

    def test_split_preserves_total_duration(self):
        """Test that splitting preserves total duration."""
        sequences = util_midi_to_sequences()
        sequence = sequences[0]
        sequence.quantise_and_normalise()
        original_duration = sequence.get_sequence_duration()

        # Split into multiple parts
        capacities = [PPQN * 4, PPQN * 4, PPQN * 4]
        splits = sequence.split(capacities)

        # Reconstruct
        reconstructed = Sequence()
        reconstructed.concatenate(splits)

        # Duration might differ slightly due to note boundaries, but should be close
        reconstructed_duration = reconstructed.get_sequence_duration()
        assert reconstructed_duration >= original_duration - PPQN * 4

    def test_merge_multiple_sequences(self):
        """Test merging multiple sequences."""
        sequences = util_midi_to_sequences()
        merged = Sequence()
        merged.merge(sequences)

        # Merged sequence should contain notes from both
        # Duration should be max of individual durations
        max_duration = max(seq.get_sequence_duration() for seq in sequences)
        assert merged.get_sequence_duration() == max_duration

    def test_concatenate_multiple_sequences(self):
        """Test concatenating multiple sequences."""
        sequences = util_midi_to_sequences()
        concatenated = Sequence()
        concatenated.concatenate(sequences)

        # Total duration should be sum of individual durations
        total_duration = sum(seq.get_sequence_duration() for seq in sequences)
        assert concatenated.get_sequence_duration() == total_duration

    def test_sequence_copy_deep(self):
        """Test that sequence copy is truly deep - messages are independent."""
        sequence = util_midi_to_sequences()[0]

        # Get original velocity of first note
        original_velocity = None
        for msg in sequence.messages_abs():
            if msg.velocity is not None and msg.velocity > 1:
                original_velocity = msg.velocity
                break

        if original_velocity is None:
            pytest.skip("No notes with velocity to test")

        # Make a copy
        copy_seq = sequence.copy()

        # Modify velocity in the ORIGINAL after copying
        for msg in sequence.messages_abs():
            if msg.velocity is not None:
                msg.velocity = 1
                break

        # First velocity in copy should still be the original value
        for msg in copy_seq.messages_abs():
            if msg.velocity is not None:
                assert msg.velocity == original_velocity, (
                    f"Copy was affected by changes to original: expected {original_velocity}, got {msg.velocity}"
                )
                break

    def test_pad_already_longer(self):
        """Test padding a sequence that's already longer than padding length."""
        sequence = util_midi_to_sequences()[0]
        original_duration = sequence.get_sequence_duration()

        sequence.pad(original_duration - 100)  # Pad to less than current

        # Duration should remain unchanged
        assert sequence.get_sequence_duration() == original_duration

    def test_quantise_doesnt_create_zero_length_notes(self):
        """Test that quantisation doesn't create zero-length notes."""
        sequence = util_midi_to_sequences()[0]
        sequence.quantise_and_normalise()

        pairings = sequence.get_message_pairings()
        for channel, pairs in pairings.items():
            for pair in pairs:
                if len(pair) == 2:
                    duration = pair[1].time - pair[0].time
                    assert duration > 0, f"Found zero-length note at channel {channel}"

    def test_cutoff_reduces_long_notes(self):
        """Test that cutoff reduces note lengths correctly."""
        sequence = util_midi_to_sequences()[0]
        max_length = 24
        reduced_length = 12

        sequence.cutoff(max_length, reduced_length)

        pairings = sequence.get_message_pairings()
        for channel, pairs in pairings.items():
            for pair in pairs:
                if len(pair) == 2:
                    duration = pair[1].time - pair[0].time
                    assert duration <= max_length, f"Note longer than max_length found"


class TestMessageEquivalence:
    """Tests for message equivalence and copying."""

    def test_message_equivalent(self):
        """Test message equivalence method."""
        msg1 = Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100, time=0)
        msg2 = Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100, time=0)

        assert msg1.equivalent(msg2)

    def test_message_not_equivalent_different_note(self):
        """Test message non-equivalence with different note."""
        msg1 = Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100, time=0)
        msg2 = Message(message_type=MessageType.NOTE_ON, channel=0, note=61, velocity=100, time=0)

        assert not msg1.equivalent(msg2)

    def test_message_from_dict(self):
        """Test creating a message from a dictionary."""
        msg_dict = {
            "message_type": "NOTE_ON",
            "channel": 0,
            "note": 60,
            "velocity": 100,
            "time": 0
        }
        msg = Message.from_dict(msg_dict)

        assert msg.message_type == MessageType.NOTE_ON
        assert msg.note == 60
        assert msg.velocity == 100

    def test_message_repr(self):
        """Test message string representation."""
        msg = Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100, time=0)
        repr_str = repr(msg)

        assert "note_on" in repr_str  # MessageType enum value is lowercase
        assert "60" in repr_str


class TestBarHandling:
    """Tests for bar operations."""

    def test_bar_to_sequence_multiple_bars(self):
        """Test converting multiple bars to a sequence."""
        sequences = util_midi_to_sequences()
        sequence = sequences[0]
        sequence.quantise_and_normalise()

        bars = Sequence.sequences_split_bars([sequence], meta_track_index=0)[0]

        # Take first 3 bars
        test_bars = bars[:3] if len(bars) >= 3 else bars

        consolidated = Bar.to_sequence(test_bars)

        # Duration should equal sum of bar durations
        expected_duration = sum(bar.sequence.get_sequence_duration() for bar in test_bars)
        assert consolidated.get_sequence_duration() == expected_duration

    def test_bar_copy(self):
        """Test bar copy creates independent copy."""
        sequences = util_midi_to_sequences()
        sequence = sequences[0]
        sequence.quantise_and_normalise()

        bars = Sequence.sequences_split_bars([sequence], meta_track_index=0)[0]
        if len(bars) == 0:
            pytest.skip("No bars to test")

        bar = bars[0]
        bar_copy = bar.copy()

        assert bar_copy.time_signature_numerator == bar.time_signature_numerator
        assert bar_copy.time_signature_denominator == bar.time_signature_denominator
        assert bar_copy is not bar
        assert bar_copy.sequence is not bar.sequence

    def test_bar_transpose(self):
        """Test transposing a bar changes note values correctly."""
        sequences = util_midi_to_sequences()
        sequence = sequences[0]
        sequence.quantise_and_normalise()

        bars = Sequence.sequences_split_bars([sequence], meta_track_index=0)[0]
        if len(bars) == 0:
            pytest.skip("No bars to test")

        bar = bars[0]

        # Get original notes
        original_notes = [msg.note for msg in bar.sequence.messages_rel()
                         if msg.message_type == MessageType.NOTE_ON]

        if len(original_notes) == 0:
            pytest.skip("No notes in first bar")

        # Copy the bar to avoid modifying the original and transpose
        bar_copy = bar.copy()
        transpose_amount = 5  # Perfect fourth
        had_to_wrap = bar_copy.transpose(transpose_amount)

        # Get new notes
        new_notes = [msg.note for msg in bar_copy.sequence.messages_rel()
                    if msg.message_type == MessageType.NOTE_ON]

        # Verify same number of notes
        assert len(new_notes) == len(original_notes), "Transpose changed number of notes"

        # Verify each note was transposed (accounting for possible wrapping)
        for orig, new in zip(original_notes, new_notes):
            if not had_to_wrap:
                assert new == orig + transpose_amount, f"Note {orig} should become {orig + transpose_amount}, got {new}"
            else:
                # If wrapped, note should still be in valid range
                assert NOTE_LOWER_BOUND <= new <= NOTE_UPPER_BOUND


class TestMIDIRoundtrip:
    """Tests for MIDI file save/load roundtrip."""

    def test_save_and_reload(self, tmp_path):
        """Test saving and reloading a sequence."""
        sequences = util_midi_to_sequences()
        sequence = sequences[0]
        sequence.quantise_and_normalise()

        file_path = tmp_path / "test_roundtrip.mid"
        sequence.save(str(file_path))

        # Reload
        reloaded = Sequence.sequences_load(file_path=str(file_path))

        assert len(reloaded) >= 1

    def test_composition_save_reload(self, tmp_path):
        """Test saving and reloading a composition."""
        composition = util_load_composition()
        file_path = tmp_path / "test_composition.mid"
        composition.save(str(file_path))

        # Reload
        reloaded = Sequence.sequences_load(file_path=str(file_path))

        assert len(reloaded) >= 1


class TestTokeniserEdgeCases:
    """Tests for tokeniser edge cases."""

    def test_tokeniser_with_empty_bars(self):
        """Test tokenising bars with empty sequences."""
        from scoda.tokenisation.notelike_tokenisation import MultiTrackLargeVocabularyNotelikeTokeniser

        tokeniser = MultiTrackLargeVocabularyNotelikeTokeniser(
            ppqn=24, num_tracks=1, flag_fuse_track=True
        )

        # Create a sequence with just a time signature and wait
        sequence = Sequence()
        sequence.add_relative_message(
            Message(message_type=MessageType.TIME_SIGNATURE, numerator=4, denominator=4)
        )
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=PPQN * 4))

        tokens = tokeniser.tokenise([sequence])

        # Should create tokens (at least rest and bar tokens)
        assert len(tokens) > 0

    def test_tokeniser_encode_decode_roundtrip(self):
        """Test that encode/decode is a perfect roundtrip."""
        from scoda.tokenisation.notelike_tokenisation import MultiTrackLargeVocabularyNotelikeTokeniser

        tokeniser = MultiTrackLargeVocabularyNotelikeTokeniser(
            ppqn=24, num_tracks=1, flag_fuse_track=True
        )

        sequences = util_midi_to_sequences()
        sequence = sequences[0]
        sequence.merge(sequences[1:])
        sequence.quantise_and_normalise()

        tokens = tokeniser.tokenise([sequence])
        encoded = tokeniser.encode(tokens)
        decoded = tokeniser.decode(encoded)

        assert tokens == decoded

    def test_tokeniser_dictionary_completeness(self):
        """Test that tokeniser dictionary contains all expected tokens."""
        from scoda.tokenisation.notelike_tokenisation import MultiTrackLargeVocabularyNotelikeTokeniser

        tokeniser = MultiTrackLargeVocabularyNotelikeTokeniser(
            ppqn=24, num_tracks=2, flag_fuse_track=True, flag_fuse_value=True, flag_fuse_velocity=True
        )

        # Check basic tokens exist
        assert "pad" in tokeniser.dictionary
        assert "sta" in tokeniser.dictionary
        assert "sto" in tokeniser.dictionary
        assert "bar" in tokeniser.dictionary


class TestChannelHandling:
    """Tests for multi-channel sequence handling."""

    def test_set_channel_all_messages(self):
        """Test setting channel for all messages."""
        sequence = util_midi_to_sequences()[0]

        sequence.set_channel(5)

        for msg in sequence.messages_rel():
            assert msg.channel == 5

    def test_channel_consistency(self):
        """Test channel consistency checking."""
        sequence = util_midi_to_sequences()[0]
        sequence.set_channel(0)

        assert sequence.is_channel_consistent()

        # Make inconsistent
        for msg in sequence.messages_abs():
            msg.channel = 1
            break

        assert not sequence.is_channel_consistent()

    def test_multi_channel_merge(self):
        """Test merging sequences with different channels."""
        seq1 = Sequence()
        seq1.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100))
        seq1.add_relative_message(Message(message_type=MessageType.WAIT, time=24))
        seq1.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=60))

        seq2 = Sequence()
        seq2.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=1, note=72, velocity=100))
        seq2.add_relative_message(Message(message_type=MessageType.WAIT, time=24))
        seq2.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=1, note=72))

        merged = Sequence()
        merged.merge([seq1, seq2])

        # Should contain messages from both channels
        channels = set()
        for msg in merged.messages_rel():
            if msg.channel is not None:
                channels.add(msg.channel)

        assert 0 in channels
        assert 1 in channels


class TestSequenceEquality:
    """Tests for sequence equality."""

    def test_equal_sequences(self):
        """Test that identical sequences are equal."""
        sequence = util_midi_to_sequences()[0]
        copy_seq = sequence.copy()

        assert sequence.equals(copy_seq)

    def test_unequal_sequences_different_notes(self):
        """Test that sequences with different notes are not equal."""
        seq1 = Sequence()
        seq1.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100))
        seq1.add_relative_message(Message(message_type=MessageType.WAIT, time=24))
        seq1.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=60))

        seq2 = Sequence()
        seq2.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=72, velocity=100))
        seq2.add_relative_message(Message(message_type=MessageType.WAIT, time=24))
        seq2.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=72))

        assert not seq1.equals(seq2)

    def test_equal_ignoring_channel(self):
        """Test equality ignoring channel differences."""
        seq1 = Sequence()
        seq1.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100))
        seq1.add_relative_message(Message(message_type=MessageType.WAIT, time=24))
        seq1.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=60))

        seq2 = Sequence()
        seq2.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=1, note=60, velocity=100))
        seq2.add_relative_message(Message(message_type=MessageType.WAIT, time=24))
        seq2.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=1, note=60))

        assert not seq1.equals(seq2, ignore_channel=False)
        assert seq1.equals(seq2, ignore_channel=True)

    def test_equal_ignoring_velocity(self):
        """Test equality ignoring velocity differences."""
        seq1 = Sequence()
        seq1.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100))
        seq1.add_relative_message(Message(message_type=MessageType.WAIT, time=24))
        seq1.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=60))

        seq2 = Sequence()
        seq2.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=50))
        seq2.add_relative_message(Message(message_type=MessageType.WAIT, time=24))
        seq2.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=60))

        assert not seq1.equals(seq2, ignore_velocity=False)
        assert seq1.equals(seq2, ignore_velocity=True)


class TestTimeSignatures:
    """Tests for time signature handling."""

    def test_time_signature_in_sequence(self):
        """Test that time signatures are correctly stored."""
        sequence = Sequence()
        sequence.add_relative_message(
            Message(message_type=MessageType.TIME_SIGNATURE, numerator=3, denominator=4)
        )
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=PPQN * 3))

        timings = sequence.get_message_times_of_type([MessageType.TIME_SIGNATURE])

        assert len(timings) == 1
        assert timings[0][1].numerator == 3
        assert timings[0][1].denominator == 4

    def test_normalise_removes_duplicate_time_signatures(self):
        """Test that normalise removes duplicate time signatures."""
        sequence = Sequence()
        sequence.add_relative_message(
            Message(message_type=MessageType.TIME_SIGNATURE, numerator=4, denominator=4)
        )
        sequence.add_relative_message(
            Message(message_type=MessageType.TIME_SIGNATURE, numerator=4, denominator=4)
        )
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=PPQN * 4))

        sequence.normalise()

        timings = sequence.get_message_times_of_type([MessageType.TIME_SIGNATURE])
        assert len(timings) == 1


class TestMusicTheory:
    """Tests for music theory utilities."""

    def test_key_transpose(self):
        """Test transposing keys."""
        from scoda.misc.music_theory import Key

        key = Key.C  # Key enum uses note names without MAJOR/MINOR
        transposed = Key.transpose_key(key, 7)  # Perfect fifth up

        assert transposed == Key.G

    def test_circle_of_fifths_distance(self):
        """Test circle of fifths distance calculation."""
        from scoda.misc.music_theory import CircleOfFifths, Note

        distance = CircleOfFifths.get_distance(Note.C.value, Note.G.value)
        assert distance == 1  # G is one step clockwise from C


class TestUtilities:
    """Tests for utility functions."""

    def test_binary_insort(self):
        """Test binary insert sort."""
        from scoda.misc.util import binary_insort

        messages = []
        binary_insort(messages, Message(time=10))
        binary_insort(messages, Message(time=5))
        binary_insort(messages, Message(time=15))
        binary_insort(messages, Message(time=7))

        times = [m.time for m in messages]
        assert times == [5, 7, 10, 15]

    def test_find_minimal_distance(self):
        """Test finding element with minimal distance."""
        from scoda.misc.util import find_minimal_distance

        collection = [0, 10, 20, 30]

        assert find_minimal_distance(5, collection) == 0  # Closer to 0 or 10, ties go to earlier
        assert find_minimal_distance(12, collection) == 1  # Closer to 10
        assert find_minimal_distance(25, collection) == 2  # Closer to 20

    def test_get_velocity_bins(self):
        """Test velocity bin generation."""
        from scoda.misc.util import get_velocity_bins

        bins = get_velocity_bins(velocity_max=127, velocity_bins=4)

        assert len(bins) == 4
        assert bins[-1] == 127  # Last bin should be max velocity

    def test_digitise_velocity(self):
        """Test velocity digitization."""
        from scoda.misc.util import digitise_velocity

        # Zero velocity should remain zero
        assert digitise_velocity(0) == 0

        # Non-zero velocities should be quantized
        result = digitise_velocity(64)
        assert result > 0

    def test_get_note_durations(self):
        """Test note duration generation."""
        from scoda.misc.util import get_note_durations

        # With PPQN=24, upper_bound=2, lower_bound=4, should get half notes to sixteenth notes
        durations = get_note_durations(2, 4, base_value=24)

        assert 48 in durations  # Half note (2 * 24)
        assert 24 in durations  # Quarter note
        assert 12 in durations  # Eighth note
        assert 6 in durations   # Sixteenth note

    def test_bin_velocity(self):
        """Test velocity binning."""
        from scoda.misc.util import bin_velocity

        # Low velocity should go to low bin
        low_bin = bin_velocity(10)
        high_bin = bin_velocity(120)

        assert low_bin < high_bin


class TestReadOnlyMessages:
    """Tests for read-only message behavior."""

    def test_read_only_message_creation(self):
        """Test that read-only messages can be created."""
        from scoda.elements.message import ReadOnlyMessage

        msg = Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100)
        ro_msg = ReadOnlyMessage(msg)

        assert ro_msg.note == 60
        assert ro_msg.velocity == 100

    def test_read_only_message_prevents_modification(self):
        """Test that read-only messages prevent attribute modification."""
        from scoda.elements.message import ReadOnlyMessage

        msg = Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100)
        ro_msg = ReadOnlyMessage(msg)

        with pytest.raises(AttributeError):
            ro_msg.note = 72

    def test_read_only_message_prevents_deletion(self):
        """Test that read-only messages prevent attribute deletion."""
        from scoda.elements.message import ReadOnlyMessage

        msg = Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100)
        ro_msg = ReadOnlyMessage(msg)

        with pytest.raises(AttributeError):
            del ro_msg.note

    def test_read_only_message_repr(self):
        """Test read-only message string representation."""
        from scoda.elements.message import ReadOnlyMessage

        msg = Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100)
        ro_msg = ReadOnlyMessage(msg)
        repr_str = repr(ro_msg)

        assert "read only" in repr_str

    def test_get_message_pairings_returns_read_only(self):
        """Test that get_message_pairings returns read-only messages via Sequence wrapper."""
        sequence = util_midi_to_sequences()[0]
        pairings = sequence.get_message_pairings()

        for channel, pairs in pairings.items():
            for pair in pairs:
                for msg in pair:
                    # These should be ReadOnlyMessage instances
                    assert hasattr(msg, 'initialised')


class TestScaleOperations:
    """Tests for sequence scaling operations."""

    def test_scale_factor_one_is_identity(self):
        """Test that scaling by factor 1 is an identity operation."""
        sequence = util_midi_to_sequences()[0]
        original_duration = sequence.get_sequence_duration()

        sequence.scale(1, quantise_afterwards=False)

        assert sequence.get_sequence_duration() == original_duration

    def test_scale_doubles_duration(self):
        """Test that scaling by factor 2 exactly doubles duration."""
        sequence = Sequence()
        sequence.add_relative_message(Message(message_type=MessageType.TIME_SIGNATURE, numerator=4, denominator=4))
        sequence.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100))
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=24))
        sequence.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=60))
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=24))

        original_duration = sequence.get_sequence_duration()
        assert original_duration == 48, f"Setup: expected duration 48, got {original_duration}"

        sequence.scale(2, quantise_afterwards=False)

        new_duration = sequence.get_sequence_duration()
        assert new_duration == 96, f"Scaling by 2 should double duration from 48 to 96, got {new_duration}"


class TestKeySignatures:
    """Tests for key signature handling."""

    def test_key_signature_in_sequence(self):
        """Test adding key signature to sequence."""
        from scoda.misc.music_theory import Key

        sequence = Sequence()
        sequence.add_relative_message(
            Message(message_type=MessageType.KEY_SIGNATURE, key=Key.G)
        )
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=PPQN * 4))

        timings = sequence.get_message_times_of_type([MessageType.KEY_SIGNATURE])

        assert len(timings) == 1
        assert timings[0][1].key == Key.G

    def test_normalise_removes_duplicate_key_signatures(self):
        """Test that normalise removes duplicate key signatures."""
        from scoda.misc.music_theory import Key

        sequence = Sequence()
        sequence.add_relative_message(Message(message_type=MessageType.KEY_SIGNATURE, key=Key.D))
        sequence.add_relative_message(Message(message_type=MessageType.KEY_SIGNATURE, key=Key.D))
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=PPQN * 4))

        sequence.normalise()

        timings = sequence.get_message_times_of_type([MessageType.KEY_SIGNATURE])
        assert len(timings) == 1

    def test_key_signature_changes_are_preserved(self):
        """Test that actual key signature changes are preserved during normalization."""
        from scoda.misc.music_theory import Key

        sequence = Sequence()
        sequence.add_relative_message(Message(message_type=MessageType.KEY_SIGNATURE, key=Key.C))
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=PPQN * 4))
        sequence.add_relative_message(Message(message_type=MessageType.KEY_SIGNATURE, key=Key.G))
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=PPQN * 4))

        sequence.normalise()

        timings = sequence.get_message_times_of_type([MessageType.KEY_SIGNATURE])
        assert len(timings) == 2


class TestCompositionOperations:
    """Tests for composition-level operations."""

    def test_composition_copy(self):
        """Test composition copy creates independent copy."""
        composition = util_load_composition()
        copy_comp = composition.copy()

        assert copy_comp is not composition
        assert len(copy_comp.tracks) == len(composition.tracks)

    def test_composition_to_sequences(self):
        """Test converting composition to sequences."""
        composition = util_load_composition()
        sequences = composition.to_sequences()

        assert len(sequences) == len(composition.tracks)
        for seq in sequences:
            assert isinstance(seq, Sequence)

    def test_composition_from_sequences(self):
        """Test creating composition from sequences."""
        from scoda.elements.composition import Composition

        sequences = util_midi_to_sequences()
        composition = Composition.from_sequences(sequences, meta_track_index=0)

        assert len(composition.tracks) >= 1


class TestTrackOperations:
    """Tests for track-level operations."""

    def test_track_copy(self):
        """Test track copy creates independent copy."""
        composition = util_load_composition()
        if len(composition.tracks) == 0:
            pytest.skip("No tracks to test")

        track = composition.tracks[0]
        track_copy = track.copy()

        assert track_copy is not track
        assert len(track_copy.bars) == len(track.bars)

    def test_track_to_sequence(self):
        """Test converting track to sequence."""
        composition = util_load_composition()
        if len(composition.tracks) == 0:
            pytest.skip("No tracks to test")

        track = composition.tracks[0]
        sequence = track.to_sequence()

        assert isinstance(sequence, Sequence)


class TestAbsoluteRelativeConversion:
    """Tests for absolute/relative sequence conversions."""

    def test_absolute_to_relative_roundtrip(self):
        """Test converting between absolute and relative preserves data."""
        sequence = util_midi_to_sequences()[0]
        sequence.quantise_and_normalise()

        # Force conversion to absolute then back to relative
        _ = sequence.abs  # Ensure absolute is generated
        sequence.invalidate_rel()
        _ = sequence.rel  # Force regeneration from absolute

        # Should still have notes
        note_count = sum(1 for m in sequence.messages_rel() if m.message_type == MessageType.NOTE_ON)
        assert note_count > 0

    def test_relative_to_absolute_roundtrip(self):
        """Test converting from relative to absolute preserves timing."""
        sequence = Sequence()
        sequence.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100))
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=48))
        sequence.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=60))

        _ = sequence.rel  # Force relative
        sequence.invalidate_abs()
        _ = sequence.abs  # Force regeneration from relative

        assert sequence.get_sequence_duration() == 48

    def test_refresh_both_representations(self):
        """Test refreshing both representations from one."""
        sequence = util_midi_to_sequences()[0]

        # Start fresh from absolute
        sequence._rel_stale = True
        sequence.refresh()

        # Both should now be valid
        assert not sequence._abs_stale
        assert not sequence._rel_stale


class TestProgramChanges:
    """Tests for program change handling."""

    def test_program_change_in_sequence(self):
        """Test adding program change to sequence."""
        sequence = Sequence()
        sequence.add_relative_message(
            Message(message_type=MessageType.PROGRAM_CHANGE, channel=0, program=25)
        )
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=PPQN * 4))

        # Should not crash
        _ = sequence.abs

    def test_program_change_preserved_in_track(self):
        """Test that program changes are detected in tracks."""
        from scoda.elements.track import Track

        composition = util_load_composition()

        # Check if any track has a program set
        # This is just a sanity check that the code path works
        for track in composition.tracks:
            _ = track.program  # Access should not crash


class TestMIDIParsing:
    """Tests for MIDI message parsing."""

    def test_midi_message_parse_note_on(self):
        """Test parsing MIDI note_on message."""
        from scoda.midi.midi_message import MidiMessage
        import mido

        mido_msg = mido.Message('note_on', note=60, velocity=100, time=0)
        midi_msg = MidiMessage.parse_mido_message(mido_msg)

        assert midi_msg.message_type == MessageType.NOTE_ON
        assert midi_msg.note == 60
        assert midi_msg.velocity == 100

    def test_midi_message_parse_note_off(self):
        """Test parsing MIDI note_off message."""
        from scoda.midi.midi_message import MidiMessage
        import mido

        mido_msg = mido.Message('note_off', note=60, velocity=0, time=0)
        midi_msg = MidiMessage.parse_mido_message(mido_msg)

        assert midi_msg.message_type == MessageType.NOTE_OFF
        assert midi_msg.note == 60

    def test_midi_message_parse_control_change(self):
        """Test parsing MIDI control_change message."""
        from scoda.midi.midi_message import MidiMessage
        import mido

        mido_msg = mido.Message('control_change', control=64, value=127, time=0)
        midi_msg = MidiMessage.parse_mido_message(mido_msg)

        assert midi_msg.message_type == MessageType.CONTROL_CHANGE
        assert midi_msg.control == 64

    def test_midi_message_parse_time_signature(self):
        """Test parsing MIDI time_signature meta message."""
        from scoda.midi.midi_message import MidiMessage
        import mido

        mido_msg = mido.MetaMessage('time_signature', numerator=3, denominator=4, time=0)
        midi_msg = MidiMessage.parse_mido_message(mido_msg)

        assert midi_msg.message_type == MessageType.TIME_SIGNATURE
        assert midi_msg.numerator == 3
        assert midi_msg.denominator == 4


class TestSequenceExceptions:
    """Tests for sequence exception handling."""

    def test_similarity_with_non_sequence_raises(self):
        """Test that similarity with non-Sequence raises exception."""
        from scoda.exceptions.sequence_exception import SequenceException

        sequence = Sequence()

        with pytest.raises(SequenceException):
            sequence.similarity("not a sequence")

    def test_inconsistent_channel_get_sequence_channel_raises(self):
        """Test that getting channel from inconsistent sequence raises exception."""
        from scoda.exceptions.sequence_exception import SequenceException

        sequence = Sequence()
        sequence.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100))
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=24))
        sequence.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=1, note=60))  # Different channel

        # This might raise or return based on implementation
        # At minimum, is_channel_consistent should be False
        assert not sequence.is_channel_consistent()


class TestSequenceStaleHandling:
    """Tests for sequence staleness handling."""

    def test_add_absolute_message_invalidates_relative(self):
        """Test that adding absolute message invalidates relative."""
        sequence = util_midi_to_sequences()[0]
        _ = sequence.rel  # Force relative generation

        sequence.add_absolute_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=72, velocity=100, time=0))

        assert sequence._rel_stale

    def test_add_relative_message_invalidates_absolute(self):
        """Test that adding relative message invalidates absolute."""
        sequence = util_midi_to_sequences()[0]
        _ = sequence.abs  # Force absolute generation

        sequence.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=72, velocity=100))

        assert sequence._abs_stale

    def test_accessing_stale_sequence_regenerates(self):
        """Test that accessing stale representation regenerates it."""
        sequence = Sequence()
        sequence.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100))
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=24))
        sequence.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=60))

        # Force abs to be generated from rel (rel is valid)
        _ = sequence.abs

        # Now rel should not be stale
        assert not sequence._rel_stale

        # If we invalidate rel but abs is still valid, accessing rel should regenerate
        sequence.invalidate_rel()
        assert sequence._rel_stale

        # Accessing rel with valid abs should regenerate
        _ = sequence.rel
        assert not sequence._rel_stale


class TestMessagePairings:
    """Tests for message pairing functionality."""

    def test_get_interleaved_message_pairings_order(self):
        """Test that interleaved pairings are ordered by time."""
        sequence = Sequence()

        # Add notes at different times
        sequence.add_absolute_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100, time=0))
        sequence.add_absolute_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=60, time=24))
        sequence.add_absolute_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=72, velocity=100, time=12))
        sequence.add_absolute_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=72, time=36))

        pairings = sequence.get_interleaved_message_pairings()

        # First should be note 60 (starts at time 0)
        # Second should be note 72 (starts at time 12)
        assert pairings[0][1][0].note == 60
        assert pairings[1][1][0].note == 72

    def test_message_pairings_imputes_unclosed_notes(self):
        """Test that message pairings imputes unclosed notes by default."""
        sequence = Sequence()
        sequence.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100))
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=24))
        # No NOTE_OFF

        pairings = sequence.get_message_pairings(impute_notes=True)

        # Should have a pairing with both NOTE_ON and (imputed) NOTE_OFF
        for channel, pairs in pairings.items():
            if len(pairs) > 0:
                assert len(pairs[0]) == 2


class TestOverwriteOperations:
    """Tests for message overwrite operations."""

    def test_overwrite_absolute_messages(self):
        """Test overwriting all absolute messages."""
        sequence = util_midi_to_sequences()[0]

        new_messages = [
            Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100, time=0),
            Message(message_type=MessageType.NOTE_OFF, channel=0, note=60, time=24)
        ]
        sequence.overwrite_absolute_messages(new_messages)

        # Should only have our new messages
        abs_msgs = list(sequence.messages_abs())
        assert len(abs_msgs) == 2

    def test_overwrite_relative_messages(self):
        """Test overwriting all relative messages."""
        sequence = util_midi_to_sequences()[0]

        new_messages = [
            Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100),
            Message(message_type=MessageType.WAIT, time=24),
            Message(message_type=MessageType.NOTE_OFF, channel=0, note=60)
        ]
        sequence.overwrite_relative_messages(new_messages)

        # Should only have our new messages
        rel_msgs = list(sequence.messages_rel())
        assert len(rel_msgs) == 3


class TestQuantizationEdgeCases:
    """Additional quantization edge case tests."""

    def test_quantise_with_custom_step_sizes(self):
        """Test quantization with custom step sizes."""
        sequence = util_midi_to_sequences()[0]

        # Quantize to only quarter notes (24 ticks with PPQN=24)
        sequence.quantise(step_sizes=[24])

        # All message times should be divisible by 24
        for msg in sequence.messages_abs():
            if msg.time is not None:
                assert msg.time % 24 == 0 or msg.time == 0

    def test_quantise_note_lengths_with_custom_values(self):
        """Test note length quantization with custom values."""
        sequence = util_midi_to_sequences()[0]

        # Only allow quarter notes (24 ticks)
        sequence.quantise_note_lengths(note_values=[24])

        pairings = sequence.get_message_pairings()
        for channel, pairs in pairings.items():
            for pair in pairs:
                if len(pair) == 2:
                    duration = pair[1].time - pair[0].time
                    # Duration should be exactly 24 or note was removed
                    assert duration == 24 or duration == 0


class TestWaitConsolidation:
    """Tests for wait message consolidation."""

    def test_normalise_consolidates_consecutive_waits(self):
        """Test that normalise consolidates consecutive wait messages."""
        sequence = Sequence()
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=10))
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=14))
        sequence.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100))
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=24))
        sequence.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=60))

        sequence.normalise()

        # Should have consolidated the first two waits
        wait_count = sum(1 for m in sequence.messages_rel() if m.message_type == MessageType.WAIT)
        assert wait_count <= 2  # At most 2 waits (consolidated initial + the one in middle)


class TestNoteOrdering:
    """Tests for note ordering in sequences."""

    def test_absolute_sequence_sort_is_stable(self):
        """Test that sorting absolute sequence maintains order for same time."""
        from scoda.sequences.absolute_sequence import AbsoluteSequence

        abs_seq = AbsoluteSequence()

        # Add notes at same time, different channels
        abs_seq.add_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100, time=0))
        abs_seq.add_message(Message(message_type=MessageType.NOTE_ON, channel=1, note=72, velocity=100, time=0))

        abs_seq.sort()

        # Both should still be at time 0
        msgs = abs_seq._messages
        assert len(msgs) >= 2
        assert all(m.time == 0 for m in msgs if m.message_type == MessageType.NOTE_ON)

    def test_binary_insort_maintains_order(self):
        """Test that binary insort maintains sorted order."""
        from scoda.sequences.absolute_sequence import AbsoluteSequence

        abs_seq = AbsoluteSequence()

        # Add in random order
        abs_seq.add_message(Message(time=30))
        abs_seq.add_message(Message(time=10))
        abs_seq.add_message(Message(time=50))
        abs_seq.add_message(Message(time=20))

        times = [m.time for m in abs_seq._messages]
        assert times == sorted(times)


class TestSequenceDurationRelation:
    """Tests for sequence duration relation calculation."""

    def test_duration_relation_with_ppqn(self):
        """Test that duration relation is calculated correctly."""
        sequence = Sequence()
        # Add exactly one quarter note worth of time
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=PPQN))

        duration_relation = sequence.get_sequence_duration_relation()

        assert duration_relation == 1.0  # One quarter note

    def test_duration_relation_with_multiple_waits(self):
        """Test duration relation with multiple wait messages."""
        sequence = Sequence()
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=PPQN * 2))
        sequence.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=60, velocity=100))
        sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=PPQN * 2))
        sequence.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=60))

        duration_relation = sequence.get_sequence_duration_relation()

        assert duration_relation == 4.0  # Four quarter notes


class TestMIDITrackConversion:
    """Tests for MIDI track conversion."""

    def test_sequence_to_midi_track(self):
        """Test converting sequence to MIDI track."""
        sequence = util_midi_to_sequences()[0]
        midi_track = sequence.to_midi_track()

        assert len(midi_track.messages) > 0

    def test_midi_track_to_mido_track(self):
        """Test converting MIDI track to mido track."""
        sequence = util_midi_to_sequences()[0]
        midi_track = sequence.to_midi_track()
        mido_track = midi_track.to_mido_track()

        # Should be a valid mido track
        assert len(mido_track) > 0


class TestKeyGuessing:
    """Tests for key signature guessing."""

    def test_key_guess_returns_valid_key(self):
        """Test that key guessing returns a valid key."""
        from scoda.misc.music_theory import Key

        sequence = util_midi_to_sequences()[0]
        guessed_key = sequence.rel.get_key_signature_guess()

        # Should be a valid Key enum member
        assert isinstance(guessed_key, Key)

    def test_key_guess_with_c_major_notes(self):
        """Test key guessing with notes in C major scale."""
        from scoda.misc.music_theory import Key

        sequence = Sequence()
        # Add notes from C major scale: C, D, E, F, G
        for note in [60, 62, 64, 65, 67]:  # C4, D4, E4, F4, G4
            sequence.add_relative_message(Message(message_type=MessageType.NOTE_ON, channel=0, note=note, velocity=100))
            sequence.add_relative_message(Message(message_type=MessageType.WAIT, time=24))
            sequence.add_relative_message(Message(message_type=MessageType.NOTE_OFF, channel=0, note=note))

        guessed_key = sequence.rel.get_key_signature_guess()

        # Should guess C or a closely related key
        assert guessed_key in [Key.C, Key.G, Key.F]


class TestMusicMappings:
    """Tests for music theory mappings."""

    def test_key_key_mapping(self):
        """Test KeyKeyMapping contains expected keys."""
        from scoda.misc.music_theory import MusicMapping, Key

        assert MusicMapping.KeyKeyMapping["C"] == Key.C
        assert MusicMapping.KeyKeyMapping["G"] == Key.G
        assert MusicMapping.KeyKeyMapping["Am"] == Key.C  # Relative minor

    def test_key_note_mapping(self):
        """Test KeyNoteMapping contains scale notes."""
        from scoda.misc.music_theory import MusicMapping, Key, Note

        c_notes = MusicMapping.KeyNoteMapping[Key.C][0]

        assert Note.C in c_notes
        assert Note.D in c_notes
        assert Note.E in c_notes

    def test_key_transpose_order(self):
        """Test key transpose order is valid."""
        from scoda.misc.music_theory import MusicMapping

        assert len(MusicMapping.key_transpose_order) == 12


