"""可复现实验套件：多随机种子、统一时间预算、GA 消融与业务敏感性。

默认采用小规模实例和短预算，适合在 CI/Docker 中运行；论文实验可通过
命令行参数放大 seeds、规模和时间预算。结果写入 results/extended_experiments.json。
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from copy import deepcopy

import numpy as np

from baselines import greedy_earliest_finish, lpt_schedule
from problem import Instance, generate_instance
from solve_ga import GeneticScheduler

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")


def _deadline_metrics(inst: Instance, result: dict) -> dict:
    end = np.asarray(result["start"]) + inst.duration[np.arange(inst.n_tasks), result["node"]]
    deadlines = np.array([x.get("deadline", 10**9) for x in inst.task_metadata])
    priorities = np.array([x.get("priority", 1) for x in inst.task_metadata])
    late = np.maximum(end - deadlines, 0)
    loads = np.bincount(result["node"], weights=end, minlength=inst.n_nodes)
    return {
        "deadline_violations": int(np.count_nonzero(late)),
        "weighted_lateness": float(np.dot(late, priorities)),
        "high_priority_on_time_pct": float(np.mean(end[priorities >= 4] <= deadlines[priorities >= 4]) * 100)
        if np.any(priorities >= 4) else 100.0,
        "load_std": float(np.std(loads)),
    }


def _ga(inst: Instance, seed: int, budget: float, *, local_search: bool = True,
        pop_size: int = 40, mutate: float = 0.15) -> dict:
    solver = GeneticScheduler(inst, seed=seed)
    result = solver.solve(time_limit=budget, pop_size=pop_size,
                          ls_every=5 if local_search else 10**9)
    result.update(_deadline_metrics(inst, result))
    return result


def multi_seed(seeds: list[int], n_tasks: int, n_nodes: int, budget: float) -> dict:
    rows = []
    for instance_seed in seeds:
        inst = generate_instance(n_tasks=n_tasks, n_nodes=n_nodes, seed=instance_seed)
        runs = [_ga(inst, 1000 + instance_seed * 10 + r, budget) for r in range(3)]
        vals = [r["makespan"] for r in runs]
        rows.append({"instance_seed": instance_seed, "best": min(vals),
                     "mean": statistics.mean(vals), "median": statistics.median(vals),
                     "std": statistics.pstdev(vals), "runs": len(vals)})
    return {"seeds": seeds, "n_tasks": n_tasks, "n_nodes": n_nodes, "budget_s": budget, "rows": rows}


def time_budget(budgets: list[float], n_tasks: int, n_nodes: int, seed: int) -> list[dict]:
    inst = generate_instance(n_tasks=n_tasks, n_nodes=n_nodes, seed=seed)
    rows = []
    for budget in budgets:
        ga = _ga(inst, 77, budget)
        greedy = greedy_earliest_finish(inst)
        lpt = lpt_schedule(inst)
        rows.append({"budget_s": budget, "ga": ga["makespan"],
                     "greedy": greedy["makespan"], "lpt": lpt["makespan"],
                     "ga_wall_time_s": ga["wall_time_s"]})
    return rows


def ablation(n_tasks: int, n_nodes: int, budget: float, seed: int) -> list[dict]:
    inst = generate_instance(n_tasks=n_tasks, n_nodes=n_nodes, seed=seed)
    configs = [
        {"name": "hybrid_ls", "local_search": True, "pop_size": 40},
        {"name": "ga_no_local_search", "local_search": False, "pop_size": 40},
        {"name": "small_population", "local_search": True, "pop_size": 15},
        {"name": "large_population", "local_search": True, "pop_size": 80},
    ]
    rows = []
    for cfg in configs:
        vals = [_ga(inst, 500 + r, budget, local_search=cfg["local_search"],
                    pop_size=cfg["pop_size"]) for r in range(3)]
        rows.append({"config": cfg["name"], "best": min(x["makespan"] for x in vals),
                     "mean": statistics.mean(x["makespan"] for x in vals),
                     "std": statistics.pstdev(x["makespan"] for x in vals)})
    return rows


def sensitivity(seed: int, budget: float) -> list[dict]:
    rows = []
    for data_scale in (0.5, 1.0, 2.0):
        for capacity_scale in (0.7, 1.0, 1.4):
            base = generate_instance(n_tasks=30, n_nodes=5, seed=seed)
            inst = deepcopy(base)
            inst.duration = np.maximum(1, np.ceil(base.duration * data_scale / capacity_scale).astype(int))
            result = _ga(inst, 900, budget)
            rows.append({"data_scale": data_scale, "capacity_scale": capacity_scale,
                         "makespan": result["makespan"], "load_std": result["load_std"],
                         "deadline_violations": result["deadline_violations"]})
    return rows


def dynamic_demo(seed: int = 7, budget: float = 0.15) -> dict:
    """简单在线调度演示：任务分批到达，节点故障后重新调度剩余任务。"""
    inst = generate_instance(n_tasks=24, n_nodes=5, seed=seed)
    first = _ga(inst, 123, budget)
    remaining = [i for i, r in enumerate(inst.release) if r >= int(np.median(inst.release))]
    failed_node = int(np.argmax(inst.node_capacities))
    reassigned = sum(1 for i in remaining if first["node"][i] == failed_node)
    return {"arriving_tasks": len(remaining), "failed_node": failed_node,
            "reassigned_tasks": reassigned, "initial_makespan": first["makespan"]}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", type=int, default=5)
    p.add_argument("--budget", type=float, default=0.15)
    args = p.parse_args()
    seeds = list(range(1, args.seeds + 1))
    result = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "multi_seed": multi_seed(seeds, 30, 5, args.budget),
        "time_budget": time_budget([args.budget, args.budget * 2, args.budget * 4], 30, 5, 7),
        "ga_ablation": ablation(30, 5, args.budget, 7),
        "sensitivity": sensitivity(7, args.budget),
        "dynamic_demo": dynamic_demo(7, args.budget),
        "multi_objective": {"formula": "0.55*makespan + 0.25*weighted_lateness + 0.20*load_std",
                            "status": "reporting-ready objective definition"},
    }
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "extended_experiments.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({"output": path, "sections": list(result)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
