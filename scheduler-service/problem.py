"""无人机群-边缘计算任务调度问题建模与实例生成。

问题场景（对应论文/简历叙事）：
一组无人机执行任务时产生若干计算任务（如目标识别、航迹规划、
传感器数据融合），任务可卸载到异构计算节点执行：
  - 节点 0        : 无人机本地计算单元（无传输开销，算力低）
  - 节点 1..M-1   : 边缘服务器（算力高，但需计入上行传输时间）

每个任务 i 有：
  - 计算量 w_i（百万周期 MCycles）
  - 释放时间 r_i（任务数据就绪时刻）
在节点 j 上的加工时间为 p_ij = ceil(w_i / f_j) + tx_ij，
其中 f_j 为节点算力，tx_ij 为传输时间（本地节点为 0）。

目标：最小化 makespan（全部任务完成时刻）。
该问题即调度理论中的 Rm | r_j | Cmax，是 NP-hard 问题，
既可用 CP-SAT 精确求解（中小规模），也适合元启发式算法（大规模）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class Instance:
    """一个调度实例。所有时间均为整数（时间片）。"""

    n_tasks: int
    n_nodes: int
    release: np.ndarray          # (n_tasks,) 任务释放时间
    duration: np.ndarray         # (n_tasks, n_nodes) 各节点加工时间
    node_names: list[str] = field(default_factory=list)
    task_metadata: list[dict[str, Any]] = field(default_factory=list)
    node_capacities: list[float] = field(default_factory=list)
    node_bandwidths: list[float] = field(default_factory=list)

    def __post_init__(self):
        if not self.node_names:
            self.node_names = ["UAV-local"] + [
                f"edge-{j}" for j in range(1, self.n_nodes)
            ]
        if not self.node_capacities:
            self.node_capacities = [1.0] + [
                float(max(1, 3 + j)) for j in range(1, self.n_nodes)
            ]
        if not self.node_bandwidths:
            self.node_bandwidths = [1.0] * self.n_nodes
        if not self.task_metadata:
            self.task_metadata = [
                {
                    "task_id": i,
                    "priority": 1,
                    "data_size_mb": 0.0,
                    "deadline": int(self.release[i] + self.duration[i].min() * 2),
                }
                for i in range(self.n_tasks)
            ]


def instance_from_specs(
    tasks: list[dict[str, Any]], nodes: list[dict[str, Any]]
) -> Instance:
    """Build an instance from imported UAV-edge task and node specifications."""
    if not tasks or not nodes:
        raise ValueError("tasks and nodes must not be empty")

    n_tasks, n_nodes = len(tasks), len(nodes)
    release = np.array([int(task.get("release_time", 0)) for task in tasks], dtype=int)
    workloads = np.array(
        [max(1.0, float(task.get("workload_mcycles", task.get("workload", 100)))) for task in tasks],
        dtype=float,
    )
    data_sizes = np.array(
        [max(0.0, float(task.get("data_size_mb", 0))) for task in tasks], dtype=float
    )
    capacities = np.array(
        [max(0.1, float(node.get("compute_capacity", node.get("capacity", 1)))) for node in nodes],
        dtype=float,
    )
    bandwidths = np.array(
        [max(0.1, float(node.get("bandwidth_mbps", node.get("bandwidth", 1)))) for node in nodes],
        dtype=float,
    )
    duration = np.ceil(workloads[:, None] / capacities[None, :]).astype(int)
    if n_nodes > 1:
        duration[:, 1:] += np.ceil(data_sizes[:, None] / bandwidths[1:][None, :]).astype(int)
    names = [str(node.get("name", f"node-{i}")) for i, node in enumerate(nodes)]
    metadata = [
        {
            "task_id": int(task.get("task_id", i)),
            "priority": int(task.get("priority", 1)),
            "data_size_mb": float(data_sizes[i]),
            "deadline": int(task.get("deadline", release[i] + duration[i].min() * 2)),
            "workload_mcycles": float(workloads[i]),
        }
        for i, task in enumerate(tasks)
    ]
    return Instance(
        n_tasks=n_tasks,
        n_nodes=n_nodes,
        release=release,
        duration=duration,
        node_names=names,
        task_metadata=metadata,
        node_capacities=capacities.tolist(),
        node_bandwidths=bandwidths.tolist(),
    )


def generate_instance(
    n_tasks: int = 30,
    n_nodes: int = 5,
    seed: int = 42,
    workload_range: tuple[int, int] = (50, 300),   # MCycles
    local_speed: float = 1.0,                       # MCycles / 时间片
    edge_speed_range: tuple[float, float] = (3.0, 6.0),
    tx_range: tuple[int, int] = (2, 10),            # 传输时间（时间片）
    release_rate: float = 0.5,                      # 释放密集度，越大任务越集中
) -> Instance:
    """生成可复现的随机实例（固定 seed 即固定数据）。"""
    rng = np.random.default_rng(seed)

    workloads = rng.integers(*workload_range, size=n_tasks)

    # 节点算力：本地低，边缘高
    speeds = np.empty(n_nodes)
    speeds[0] = local_speed
    speeds[1:] = rng.uniform(*edge_speed_range, size=n_nodes - 1)

    # 传输时间：本地为 0，边缘节点每任务一个上行延迟
    tx = np.zeros((n_tasks, n_nodes), dtype=int)
    tx[:, 1:] = rng.integers(*tx_range, size=(n_tasks, n_nodes - 1))

    duration = np.ceil(workloads[:, None] / speeds[None, :]).astype(int)
    duration += tx

    # 释放时间：以平均加工时间为尺度，release_rate 越大越拥挤
    avg_p = duration.mean()
    horizon = avg_p * n_tasks / n_nodes * release_rate
    release = rng.integers(0, max(2, int(horizon)), size=n_tasks)

    task_metadata = [
        {
            "task_id": i,
            "priority": int(rng.integers(1, 6)),
            "data_size_mb": float(rng.integers(5, 51)),
            "deadline": int(release[i] + duration[i].min() * 2),
            "workload_mcycles": float(workloads[i]),
        }
        for i in range(n_tasks)
    ]
    return Instance(
        n_tasks,
        n_nodes,
        release,
        duration,
        task_metadata=task_metadata,
        node_capacities=speeds.tolist(),
        node_bandwidths=[1.0] * n_nodes,
    )


def makespan_of(assignment: np.ndarray, order: np.ndarray,
                inst: Instance) -> tuple[int, np.ndarray, np.ndarray]:
    """通用解码器：按 order 顺序把任务放到指定节点的最早可用时刻。

    返回 (makespan, start_times, node_ids)。
    元启发式算法与精确解的结果核对都可复用此函数。
    """
    node_free = np.zeros(inst.n_nodes, dtype=int)
    start = np.zeros(inst.n_tasks, dtype=int)
    for i in order:
        j = int(assignment[i])
        s = max(node_free[j], inst.release[i])
        start[i] = s
        node_free[j] = s + inst.duration[i, j]
    end = start + inst.duration[np.arange(inst.n_tasks), assignment]
    return int(end.max()), start, assignment
