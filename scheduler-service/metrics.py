"""Metrics shared by benchmark scripts and API integrations."""
from __future__ import annotations

import math
from collections.abc import Iterable


def relative_gap(value: float, reference: float) -> float:
    """Return percentage gap from a positive reference objective."""
    if reference <= 0:
        raise ValueError("reference must be positive")
    return (value - reference) / reference * 100.0


def summarize_runs(runs: Iterable[dict], reference: float | None = None) -> dict:
    """Summarize repeated runs without hiding variability."""
    rows = list(runs)
    if not rows:
        raise ValueError("at least one run is required")
    makespans = [float(row["makespan"]) for row in rows]
    summary = {
        "runs": len(rows),
        "best": int(min(makespans)),
        "average": sum(makespans) / len(makespans),
        "std": math.sqrt(sum((x - sum(makespans) / len(makespans)) ** 2
                             for x in makespans) / len(makespans)),
    }
    if reference is not None:
        summary["gap_pct"] = relative_gap(summary["best"], reference)
    return summary
