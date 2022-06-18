import copy

from sCoda import Message, Composition, Sequence, Bar
from sCoda.elements.message import MessageType
from sCoda.util.music_theory import Key


def test_message_representation():
    msg = Message(message_type=MessageType.note_on, note=42, velocity=127, control=0, numerator=4, denominator=4,
                  key=Key.c, time=10)

    representation = msg.__repr__()

    assert "42" in representation


def test_stuff():
    composition = Composition.from_midi_file("resources/beethoven_o27-2_m3.mid", [[1], [2]], [0, 3])

    assert len(composition.tracks) == 2

    return composition


def test_difficulty():
    sequence = Sequence.from_midi_file("resources/0001_14Petite Etude.zip_4.mid", [[0]], [0])[0]
    num = 4
    den = 4

    for msg in sequence.rel.messages:
        if msg.message_type == MessageType.time_signature:
            num = msg.numerator
            den = msg.denominator
            break

    print()
    bar = Bar(sequence, num, den)

    x = bar.sequence
    bar.difficulty()

    print(f"Note Amount: {x._diff_note_amount}")
    print(f"Note Values: {x._diff_note_values}")
    print(f"Note Classes: {x._diff_note_classes}")
    print(f"Concurrent Notes: {x._diff_concurrent_notes}")
    print(f"Key: {x._diff_key}")
    print(f"Accidentals: {x._diff_accidentals}")
    print(f"Distances: {x._diff_distances}")
    print(f"Rhythm: {x._diff_rhythm}")
    print(f"Pattern: {x._diff_pattern}")
    print(f"Overall Difficulty: {bar.difficulty()}")


def test_concurrent():
    sequence = Sequence.from_midi_file("resources/beethoven_o27-2_m3.mid", [[0]], [0])[0]

    seq_lead = sequence
    seq_acmp = copy.copy(sequence)
    seq_acmp.transpose(-12)

    lead_abs = seq_lead.abs._get_absolute_note_array()
    acmp_abs = seq_acmp.abs._get_absolute_note_array()

    print()

    for entry in lead_abs:
        fitting = []
        for a_entry in acmp_abs:
            if a_entry[0].time <= entry[1].time:
                fitting.append(a_entry)
            else:
                break
        print(entry)
        print(fitting)
        print()

        for fit in fitting:
            if fit[0].note <= entry[0].note:
                pass
            else:
                if fit[1].time <= entry[0].time:
                    pass
                else:
                    print("noted violation")

            acmp_abs.remove(fit)
