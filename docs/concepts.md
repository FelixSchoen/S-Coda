# Musical values

## Time and intervals

All note positions, event times, durations, slices, and bar spans are integer ticks. `ticks_per_quarter` defines the
resolution. Notes use half-open intervals: a note with `start=0` and `end=24` sounds for ticks 0 through 23 and may be
followed by another note with the same channel and pitch at tick 24.

`Sequence.duration_ticks` may extend beyond its last note or event so trailing silence is represented explicitly. It
must never end before contained data. A sequence stores notes and events in canonical order, making equality and
serialisation deterministic.

## Events

S-Coda represents time signatures, key signatures, tempi, controller changes, and program changes as separate immutable
types. Global events are emitted from the selected metadata track during MIDI export; channel events remain on their
own tracks.

## Transformations

Sequence methods such as `transpose()`, `quantise()`, `resample()`, `slice()`, and `with_velocity()` return new values.
`merge()` overlays sequences, while `concatenate()` offsets them in time. Operations that would be ambiguous or lose
required information raise a `ScodaError` subclass.

## Bars and context

`bar_spans()` calculates meter-aware intervals from one sequence. `split_bars()` accepts multiple synchronised tracks
and returns a track-major tuple: the outer tuple contains tracks and each inner tuple contains that track's bars.

By default, each bar receives the meter, key, tempo, program, and controller state active at its boundary. Program and
controller changes are replayed in their original order because MIDI bank selection, RPN, and NRPN commands are
order-sensitive; a contextual bar can therefore contain their ordered history rather than only one event per controller.
Pass `carry_context=False` only when raw event-window slices are required.
