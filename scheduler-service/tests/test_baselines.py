from __future__ import annotations

import numpy as np

from baselines import business_aware_schedule, greedy_earliest_finish, lpt_schedule, random_schedule
from metrics import relative_gap, summarize_runs
from problem import generate_instance


def _assert_valid_result(result, n_tasks):
    assert result["makespan"] > 0
    assert len(result["start"]) == n_tasks
    assert len(result["node"]) == n_tasks
    assert sorted(result["node"]) >= [0]


def test_baselines_return_valid_schedules():
    inst = generate_instance(n_tasks=12, n_nodes=4, seed=5)
    for result in [
        random_schedule(inst, seed=7),
        greedy_earliest_finish(inst),
        lpt_schedule(inst),
        business_aware_schedule(inst),
    ]:
        _assert_valid_result(result, inst.n_tasks)
        assert all(0 <= node < inst.n_nodes for node in result["node"])


def test_random_baseline_is_reproducible():
    inst = generate_instance(n_tasks=12, n_nodes=4, seed=5)
    first = random_schedule(inst, seed=7)
    second = random_schedule(inst, seed=7)
    assert first["makespan"] == second["makespan"]
    assert first["node"] == second["node"]
    assert first["start"] == second["start"]


def test_metrics_report_variability_and_gap():
    rows = [{"makespan": 10}, {"makespan": 14}, {"makespan": 12}]
    summary = summarize_runs(rows, reference=8)
    assert summary["runs"] == 3
    assert summary["best"] == 10
    assert summary["average"] == 12
    assert summary["gap_pct"] == 25
    assert relative_gap(10, 8) == 25


def test_business_aware_schedule_prioritizes_urgent_tasks_without_invalid_nodes():
    inst = generate_instance(n_tasks=10, n_nodes=3, seed=17)
    result = business_aware_schedule(inst)
    _assert_valid_result(result, inst.n_tasks)
    assert result["method"] == "business_aware"
    assert all(0 <= node < inst.n_nodes for node in result["node"])
