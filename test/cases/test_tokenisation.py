from base import *
from scoda.utils.tokenisation import NotelikeTokeniser


def test_absolute_notelike_tokenisation():
    tokeniser = NotelikeTokeniser(running_value=True, running_time_sig=True)
    sequences = Sequence.from_midi_file(file_path=RESOURCE_SWEEP)
    sequence = sequences[0]

    print(tokeniser.tokenise(sequence))
