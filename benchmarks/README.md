# Release benchmarks

The benchmark module is a local release check for MIDI import, sequence transformation, tokenisation, and constrained
decoding. It is deliberately not a hosted-CI timing gate because shared runners are too noisy for reliable comparisons.
Run it as a module from the repository root so Python measures the checked-out source rather than another installed copy.

Capture a baseline from the release candidate on an otherwise idle machine:

```bash
python -m benchmarks.benchmark_release --runs 7 --warmups 2 --output /tmp/scoda-baseline.json
```

After a code or dependency change, repeat the benchmark on the same machine, Python version, power profile, and working
tree, then compare it with the captured baseline:

```bash
python -m benchmarks.benchmark_release --runs 7 --warmups 2 \
  --compare /tmp/scoda-baseline.json --output /tmp/scoda-candidate.json
```

Runtime and traced Python memory are measured in separate passes so allocation tracing does not distort timing. Traced
memory does not include most native allocations made by Mido, the Python runtime, or optional numerical libraries.

The release is blocked when the median runtime or peak traced Python memory of any stable scenario exceeds the baseline
by more than 10%. Improvements are accepted without an upper bound. Investigate measurements with a high relative MAD,
close background applications, and rerun before treating a marginal result as a regression. The comparison command
requires exactly matching Python/platform metadata and scenario names; baselines from any other environment are
rejected rather than treated as evidence of improvement or regression. Run and warmup counts must also match. The
candidate JSON is still written when the threshold blocks a release, preserving the evidence needed for diagnosis.

Capture a new baseline whenever a scenario is added or renamed. The constraint benchmarks separate a cold
tokeniser-and-mask trace from repeated warm-cache lookups over the same realistic generation trace.
