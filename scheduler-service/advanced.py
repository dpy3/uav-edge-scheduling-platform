"""动态重调度与多目标评价的轻量扩展。

这些函数不改变现有 makespan 求解器，便于在在线系统中对新到达任务或故障
节点执行快速重调度，并用统一权重评价时延、迟延和负载均衡。
"""
from __future__ import annotations

import numpy as np

from problem import Instance, makespan_of


def weighted_objective(inst: Instance, result: dict, *, alpha: float = 0.55,
                       beta: float = 0.25, gamma: float = 0.20) -> dict:
    """计算 makespan、加权迟延和负载方差组成的可解释多目标分数。"""
    mk, start, node = makespan_of(np.asarray(result["node"]),
                                  np.argsort(np.asarray(start := result["start"])), inst)
    end = start + inst.duration[np.arange(inst.n_tasks), node]
    deadlines = np.array([x.get("deadline", mk) for x in inst.task_metadata])
    priorities = np.array([x.get("priority", 1) for x in inst.task_metadata])
    late = np.maximum(end - deadlines, 0)
    loads = np.bincount(node, weights=end, minlength=inst.n_nodes)
    lateness = float(np.dot(late, priorities))
    load_std = float(np.std(loads))
    score = alpha * mk + beta * lateness + gamma * load_std
    return {"makespan": int(mk), "weighted_lateness": lateness,
            "load_std": load_std, "score": float(score)}


def reschedule_after_node_failure(inst: Instance, result: dict, failed_node: int) -> dict:
    """节点故障后将受影响任务迁移到其余节点，并返回新的可行解。"""
    if failed_node < 0 or failed_node >= inst.n_nodes:
        raise ValueError("failed_node out of range")
    assignment = np.asarray(result["node"], dtype=int).copy()
    affected = np.flatnonzero(assignment == failed_node)
    available = [j for j in range(inst.n_nodes) if j != failed_node]
    if not available:
        raise ValueError("at least one node must remain available")
    for task in affected:
        assignment[task] = min(available, key=lambda j: inst.duration[task, j])
    order = np.argsort(np.asarray(result.get("start", np.zeros(inst.n_tasks))), kind="stable")
    mk, start, node = makespan_of(assignment, order, inst)
    return {"makespan": int(mk), "start": start.tolist(), "node": node.tolist(),
            "failed_node": int(failed_node), "reassigned_tasks": int(len(affected))}
