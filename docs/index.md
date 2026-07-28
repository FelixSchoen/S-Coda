# S-Coda

S-Coda provides deterministic symbolic-music processing for machine-learning workflows. Its public model is built from
immutable notes, timed events, and sequences. Every constructor validates its invariants, every transformation returns
a new value, and every serialisation boundary reports information that could affect reproducibility.

The library includes:

- validated MIDI import with repair, strict, and lossless policies;
- deterministic MIDI export and explicit rejection of ambiguous note overlaps;
- quantisation, transposition, resampling, slicing, composition, and contextual bar splitting;
- a canonical notelike token grammar with immutable configuration;
- vocabulary manifests and SHA-256 fingerprints;
- incremental grammar state for constrained generation.

Install S-Coda with:

```bash
python -m pip install scoda
```

All supported names are imported directly from `scoda`. The package supports Python 3.11 through 3.14.

Continue with the [quick start](quickstart.md), or use the [API reference](api.md) when you already know the concept you
need.
