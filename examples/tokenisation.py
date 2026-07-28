"""Executable tokenisation example used by the documentation."""

from scoda import Note, NotelikeConfig, NotelikeTokeniser, Sequence


def main() -> None:
    config = NotelikeConfig(
        num_tracks=2,
        pitch_range=(48, 84),
        note_values=(6, 12, 24),
        velocity_bins=127,
    )
    tokeniser = NotelikeTokeniser(config)
    tracks = (
        Sequence((Note(0, 12, 60, 80),), (), 96, 24),
        Sequence((Note(24, 48, 67, 100, 1),), (), 96, 24),
    )

    body = tokeniser.tokenise_body(tracks)
    complete = tokeniser.frame(body)
    assert tokeniser.unframe(complete) == body
    assert tokeniser.detokenise(complete) == tracks

    state = tokeniser.initial_state()
    for token_id in tokeniser.encode(complete):
        assert token_id in tokeniser.allowed_token_ids(state)
        state = tokeniser.advance(state, token_id)
    assert state.ended
    assert tokeniser.manifest.codec_id == "notelike"


if __name__ == "__main__":
    main()
