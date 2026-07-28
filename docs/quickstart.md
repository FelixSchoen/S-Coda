# Quick start

This executable example constructs an immutable sequence, transforms and tokenises it, inspects aligned metadata, and
round-trips it through a temporary MIDI file:

```python
--8<-- "examples/quickstart.py"
```

The important rule is that transformations do not mutate their receiver. Always assign the returned sequence. A
tokeniser likewise has immutable configuration and a deterministic vocabulary for that configuration.

Use `SequenceBuilder` when notes or events are accumulated incrementally. Use the immutable `Sequence` constructor when
all values are already available.
