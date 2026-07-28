"""Executable MIDI-diagnostics example used by the documentation."""

import mido

from scoda import MidiImportError, load_midi


def main() -> None:
    midi_file = mido.MidiFile(ticks_per_beat=24)
    midi_file.tracks.append(
        mido.MidiTrack(
            [
                mido.Message("note_off", note=61, channel=0, time=0),
                mido.Message("note_on", note=60, velocity=90, channel=0, time=3),
                mido.MetaMessage("end_of_track", time=9),
            ]
        )
    )

    repaired = load_midi(midi_file, mode="repair")
    assert {diagnostic.code for diagnostic in repaired.report.errors} == {
        "unclosed_note",
        "unmatched_note_off",
    }

    try:
        load_midi(midi_file, mode="strict")
    except MidiImportError as error:
        assert error.report == repaired.report
    else:  # pragma: no cover - executable documentation assertion
        raise AssertionError("strict import unexpectedly accepted malformed MIDI")


if __name__ == "__main__":
    main()
