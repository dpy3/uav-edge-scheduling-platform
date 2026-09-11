"""Simple scheduling baselines used to calibrate the heuristic solver."""
from __future__ import annotations

import time

import numpy as np

from problem import Instance, makespan_of


def _result(assignment: np.ndarray, order: np.ndarray, inst: Instance,
            elapsed: float, name: str) -> dict:
    makespan, start, node = makespan_of(assignment, order, inst)
    return {
        "method": name,
        "makespan": int(makespan),
        "wall_time_s": round(elapsed, 6),
        "start": start.tolist(),
        "node": node.tolist(),
    }


def random_schedule(inst: Instance, seed: int = 0) -> dict:
    """Build a reproducible random assignment and release-time order."""
    started = time.perf_counter()
    rng = np.random.default_rng(seed)
    assignment = rng.integers(0, inst.n_nodes, size=inst.n_tasks)
    # Keep the order feasible and deterministic while retaining randomness
    # among tasks released at the same time.
    tie_break = rng.random(inst.n_tasks)
    order = np.lexsort((tie_break, inst.release))
    return _result(assignment, order, inst, time.perf_counter() - started,
                   "random")


def greedy_earliest_finish(inst: Instance) -> dict:
    """Assign each task to the node producing the earliest local finish time."""
    started = time.perf_counter()
    order = np.argsort(inst.release, kind="stable")
    assignment = np.empty(inst.n_tasks, dtype=int)
    node_free = np.zeros(inst.n_nodes, dtype=int)

    for task in order:
        finishes = np.maximum(node_free, inst.release[task])
        finishes = finishes + inst.duration[task]
        node = int(np.argmin(finishes))
        assignment[task] = node
        node_free[node] = int(finishes[node])

    return _result(assignment, order, inst,
                   time.perf_counter() - started, "greedy_earliest_finish")


def lpt_schedule(inst: Instance) -> dict:
    """Longest-processing-time-first with earliest-finish assignment."""
    started = time.perf_counter()
    min_duration = inst.duration.min(axis=1)
    order = np.lexsort((inst.release, -min_duration))
    assignment = np.empty(inst.n_tasks, dtype=int)
    node_free = np.zeros(inst.n_nodes, dtype=int)

    for task in order:
        finishes = np.maximum(node_free, inst.release[task])
        finishes = finishes + inst.duration[task]
        node = int(np.argmin(finishes))
        assignment[task] = node
        node_free[node] = int(finishes[node])

    return _result(assignment, order, inst, time.perf_counter() - started,
                   "lpt")


def business_aware_schedule(inst: Instance) -> dict:
    """优先级/截止时间感知的快速启发式。

    先处理释放时间早、优先级高且剩余裕量小的任务，再按“预计完工时间
    + 加权迟延惩罚”选择节点。该方法用于业务场景，不替代 makespan 基线。
    """
    started = time.perf_counter()
    priorities = np.array([x.get("priority", 1) for x in inst.task_metadata])
    deadlines = np.array([x.get("deadline", 10**9) for x in inst.task_metadata])
    min_duration = inst.duration.min(axis=1)
    slack = deadlines - inst.release - min_duration
    order = np.lexsort((slack, -priorities, inst.release))
    assignment = np.empty(inst.n_tasks, dtype=int)
    node_free = np.zeros(inst.n_nodes, dtype=int)
    for task in order:
        starts = np.maximum(node_free, inst.release[task])
        finishes = starts + inst.duration[task]
        tardiness = np.maximum(finishes - deadlines[task], 0)
        score = finishes + tardiness * (1.0 + priorities[task])
        node = int(np.argmin(score))
        assignment[task] = node
        node_free[node] = int(finishes[node])
    return _result(assignment, order, inst,
                   time.perf_counter() - started, "business_aware")


def run_baselines(inst: Instance, seed: int = 0) -> list[dict]:
    """Return all lightweight baselines in a stable reporting order."""
    return [
        random_schedule(inst, seed=seed),
        greedy_earliest_finish(inst),
        lpt_schedule(inst),
        business_aware_schedule(inst),
    ]
