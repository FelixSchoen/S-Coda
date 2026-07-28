# MIDI import and export

`load_midi()` accepts a path or a `mido.MidiFile` and always returns `MidiLoadResult`. Inspect its `report` before using
material imported with the repair policy.

## Import policies

| Mode | Repairs malformed input | Permits ignored unsupported messages |
| --- | --- | --- |
| `repair` | Yes, with diagnostics | Yes, with diagnostics |
| `strict` | No | Yes, with diagnostics |
| `lossless` | No | No |

Rejected imports raise `MidiImportError`; its `report` attribute contains the complete diagnostic report. Diagnostics
use stable machine-readable `code` values and human-readable `details`.

```python
--8<-- "examples/midi_diagnostics.py"
```

## Deterministic repairs

Repair mode closes notes left active at a track endpoint, discards unmatched note-off messages, resolves same-key
retriggers into adjacent intervals, and canonicalises representable same-tick ordering. Every such change is reported.
PPQN scaling uses exact rational arithmetic before integer rounding.

## Lossless limits

Independent timelines in MIDI format 2 cannot be represented by one synchronised sequence collection and are rejected.
Lossless mode also rejects non-integral PPQN resampling and ignored messages. Note-off velocity and all standard
time-signature bytes are preserved.

## Export

`to_mido()` constructs a deterministic `mido.MidiFile`; `save_midi()` writes the same representation. Tracks must share
one PPQN. Overlapping notes with the same channel and pitch are rejected because ordinary MIDI note-off messages cannot
identify which overlapping interval ends.
