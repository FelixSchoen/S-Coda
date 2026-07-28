# Reproducible experiments

Persist enough information to reconstruct and validate every symbolic-music dataset:

- the S-Coda package version;
- `tokeniser.manifest.codec_id`;
- `tokeniser.manifest.normalised_config`;
- `tokeniser.manifest.size` and `tokeniser.manifest.sha256`;
- the Python version, operating system, architecture, and relevant hardware;
- the MIDI import mode and any retained diagnostic report.

Reconstruct serialised tokenisers with `create_tokeniser("notelike", config)`. Before combining a dataset and model,
compare their manifest fingerprints and vocabulary sizes and reject the operation on a mismatch.

For an exact development tool set, install the checked-in hashed lock file before the package:

```bash
python -m pip install --require-hashes -r requirements.lock
python -m pip install --no-deps .
```

## Performance policy

The local release benchmark covers MIDI loading, quantisation and bar splitting, tokenisation, and cold and warm
constraint-state traces. Capture and compare baselines on the same idle machine, interpreter, platform, and power
profile. A release is blocked when median runtime or peak traced Python memory regresses by more than 10%; improvements
are accepted without a limit. See `benchmarks/README.md` for exact commands and measurement caveats.
