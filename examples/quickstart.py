"""Executable end-to-end S-Coda example used by the documentation."""

from pathlib import Path
from tempfile import TemporaryDirectory

from scoda import Note, NotelikeConfig, NotelikeTokeniser, Sequence, load_midi, save_midi


def main() -> None:
    sequence = Sequence(
        notes=(Note(0, 24, 60, 96), Note(24, 48, 64, 88)),
        duration_ticks=96,
        ticks_per_quarter=24,
    )
    sequence = sequence.quantise_and_normalise((3, 6, 12, 24), (6, 12, 24))

    tokeniser = NotelikeTokeniser(NotelikeConfig(note_values=(6, 12, 24), velocity_bins=127))
    tokens = tokeniser.tokenise((sequence,))
    token_ids = tokeniser.encode(tokens)
    assert tokeniser.decode(token_ids) == tokens
    assert tokeniser.detokenise(tokens) == (sequence,)
    assert len(tokeniser.metadata(tokens)) == len(tokens)

    with TemporaryDirectory() as directory:
        destination = Path(directory) / "example.mid"
        save_midi((sequence,), destination)
        loaded = load_midi(destination, mode="strict")
        assert loaded.sequences == (sequence,)


if __name__ == "__main__":
    main()
