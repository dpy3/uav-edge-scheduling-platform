"""精确求解基线：用 PyJobShop（OR-Tools CP-SAT）求解实例。

建模说明：
  - 每个计算任务 -> 一个只含单个 task 的 job，job 的 release_date
    即任务的释放时间 r_i；
  - 每个计算节点 -> 一台 machine；
  - 任务在节点 j 的加工 -> 一个 mode，duration = p_ij；
  - 目标：最小化 makespan。
"""
from __future__ import annotations

import json
import time

from pyjobshop import Model

from problem import Instance, generate_instance


def solve_instance(inst: Instance, time_limit: float = 60.0,
                   num_workers: int | None = None) -> dict:
    model = Model()

    machines = [model.add_machine(name=name) for name in inst.node_names]
    tasks = []
    for i in range(inst.n_tasks):
        job = model.add_job(release_date=int(inst.release[i]),
                            name=f"task-{i}")
        task = model.add_task(job=job, name=f"task-{i}")
        tasks.append(task)

    for i, task in enumerate(tasks):
        for j, machine in enumerate(machines):
            model.add_mode(task, machine, duration=int(inst.duration[i, j]))

    model.set_objective(weight_makespan=1)

    t0 = time.perf_counter()
    result = model.solve(solver="ortools", time_limit=time_limit,
                         display=False, num_workers=num_workers)
    elapsed = time.perf_counter() - t0

    start = [None] * inst.n_tasks
    node_of = [None] * inst.n_tasks
    for i, st in enumerate(result.best.tasks):
        start[i] = st.start
        node_of[i] = st.resources[0]

    return {
        "status": str(result.status),
        "makespan": int(result.best.objective),
        "wall_time_s": round(elapsed, 2),
        "start": start,
        "node": node_of,
    }


if __name__ == "__main__":
    inst = generate_instance(n_tasks=40, n_nodes=5, seed=7)
    res = solve_instance(inst, time_limit=30)
    print(json.dumps({k: v for k, v in res.items()
                      if k not in ("start", "node")}, ensure_ascii=False))
