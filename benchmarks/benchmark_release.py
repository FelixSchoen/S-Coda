"""Repeatable local release benchmarks; measurements are not CI timing gates."""

from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import time
import tracemalloc
from pathlib import Path

import scoda
from scoda import Note, NotelikeConfig, NotelikeTokeniser, Sequence, load_midi, split_bars

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _positive_finite_measurement(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return float(value)


def _measure_runtime(function, warmups: int, runs: int) -> tuple[list[float], float]:
    for _ in range(warmups):
        function()
    timings = []
    for _ in range(runs):
        started = time.perf_counter_ns()
        function()
        timings.append((time.perf_counter_ns() - started) / 1_000_000)
    median = statistics.median(timings)
    relative_mad = statistics.median(abs(value - median) for value in timings) / median if median else 0.0
    return timings, relative_mad


def _measure_peak_python_memory(function, runs: int) -> float:
    peaks = []
    for _ in range(runs):
        tracemalloc.start()
        function()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peaks.append(peak / 1024 / 1024)
    return max(peaks)


def _measure(function, warmups: int, runs: int) -> dict[str, float]:
    timings, relative_mad = _measure_runtime(function, warmups, runs)
    return {
        "median_ms": statistics.median(timings),
        "peak_python_memory_mib": _measure_peak_python_memory(function, runs),
        "relative_mad": relative_mad,
    }


def _baseline_memory_mib(measurement: dict[str, float]) -> float:
    return _positive_finite_measurement(
        measurement.get("peak_python_memory_mib"), name="baseline peak_python_memory_mib"
    )


def _synthetic() -> tuple[Sequence, ...]:
    duration = 24 * 4 * 256
    return tuple(
        Sequence(
            tuple(
                Note(start, start + 12, 48 + (index % 36), 64 + (index % 63), track)
                for index, start in enumerate(range(track * 2, duration - 12, 24))
            ),
            (),
            duration,
            24,
        )
        for track in range(6)
    )


def _environment() -> dict[str, str]:
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }


def main() -> None:
    imported_package = Path(scoda.__file__).resolve().parent
    source_package = (_PROJECT_ROOT / "scoda").resolve()
    if imported_package != source_package:
        raise SystemExit(
            "benchmark imported S-Coda from outside this checkout; "
            "run it from the repository root with 'python -m benchmarks.benchmark_release'"
        )
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--compare")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.runs <= 0:
        parser.error("--runs must be positive")
    if args.warmups < 0:
        parser.error("--warmups must be non-negative")
    corpus = sorted((_PROJECT_ROOT / "test/res").glob("*.mid"))
    if not corpus:
        raise SystemExit("release benchmark corpus is empty")
    sequences = _synthetic()
    tokeniser = NotelikeTokeniser(
        NotelikeConfig(
            ticks_per_quarter=24,
            num_tracks=6,
            pitch_range=(48, 83),
            note_values=(12,),
            velocity_bins=8,
        )
    )
    tokens = tokeniser.tokenise(sequences)
    trace_states = []
    trace_state = tokeniser.initial_state()
    for token_id in tokeniser.encode(tokens[:256]):
        trace_states.append(trace_state)
        trace_state = tokeniser.advance(trace_state, token_id)
    for state in trace_states:
        tokeniser.allowed_token_ids(state)

    def warm_constraint_trace() -> None:
        for _ in range(25):
            for state in trace_states:
                tokeniser.allowed_token_ids(state)

    def cold_constraint_trace() -> None:
        cold_tokeniser = NotelikeTokeniser(tokeniser.config)
        state = cold_tokeniser.initial_state()
        for token in tokens[:256]:
            cold_tokeniser.allowed_token_ids(state)
            state = cold_tokeniser.advance(state, cold_tokeniser.token_to_id[token])

    scenarios = {
        "midi_load_corpus": lambda: [load_midi(path, target_ticks_per_quarter=24) for path in corpus],
        "quantise_and_split": lambda: split_bars(
            tuple(
                sequence.quantise_and_normalise((3, 4, 6, 8, 12, 16, 24), (3, 4, 6, 8, 12, 16, 24))
                for sequence in sequences
            )
        ),
        "tokenise": lambda: tokeniser.tokenise(sequences),
        "constraint_trace_cold": cold_constraint_trace,
        "constraint_trace_warm": warm_constraint_trace,
    }
    result = {
        "environment": _environment(),
        "runs": args.runs,
        "warmups": args.warmups,
        "scenarios": {name: _measure(function, args.warmups, args.runs) for name, function in scenarios.items()},
    }
    blocked = False
    if args.compare:
        baseline = json.loads(Path(args.compare).read_text())
        if not isinstance(baseline, dict):
            raise ValueError("baseline must contain a JSON object")
        if baseline.get("environment") != result["environment"]:
            raise ValueError("baseline environment does not match the current Python and platform")
        if baseline.get("runs") != args.runs or baseline.get("warmups") != args.warmups:
            raise ValueError("baseline runs and warmups do not match the current benchmark")
        baseline_scenarios = baseline.get("scenarios")
        if not isinstance(baseline_scenarios, dict):
            raise ValueError("baseline has no scenarios object")
        if set(baseline_scenarios) != set(scenarios):
            missing = sorted(set(scenarios) - set(baseline_scenarios))
            extra = sorted(set(baseline_scenarios) - set(scenarios))
            raise ValueError(f"baseline scenario set differs: missing={missing}, extra={extra}")
        regressions = {}
        for name, measurement in result["scenarios"].items():
            previous = baseline_scenarios[name]
            if not isinstance(previous, dict):
                raise ValueError(f"baseline scenario {name!r} must be an object")
            try:
                previous_runtime = _positive_finite_measurement(
                    previous.get("median_ms"), name=f"baseline scenario {name!r} median_ms"
                )
            except ValueError as exc:
                raise ValueError(f"baseline scenario {name!r} has no positive finite median_ms") from exc
            regressions[name] = {
                "runtime_ratio": measurement["median_ms"] / previous_runtime,
                "memory_ratio": measurement["peak_python_memory_mib"] / _baseline_memory_mib(previous),
            }
        result["comparison"] = regressions
        blocked = any(
            values[metric] > 1.10 for values in regressions.values() for metric in ("runtime_ratio", "memory_ratio")
        )
    rendered = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n")
    print(rendered)
    if blocked:
        raise SystemExit("release blocked: a stable benchmark regressed by more than 10%")


if __name__ == "__main__":
    main()
