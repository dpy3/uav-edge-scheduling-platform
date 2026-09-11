"""对比实验：CP-SAT 精确求解 vs 混合遗传算法。

在 5 种规模的无人机-边缘计算调度实例上分别求解，输出：
  - results/experiments.json : 量化对比表（makespan / gap / 耗时 / 状态）
  - results/convergence.png  : GA 收敛曲线
  - results/gantt_<scale>.png: 甘特图（两种求解器各一张）

结果增量写盘，中断后可断点续跑。
"""
from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from problem import generate_instance
from baselines import run_baselines
from solve_cpsat import solve_instance
from solve_ga import GeneticScheduler

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)
JSON_PATH = os.path.join(OUT, "experiments.json")

SCALES = [
    ("20x4", 20, 4, 11),
    ("40x5", 40, 5, 7),
    ("80x8", 80, 8, 21),
    ("150x10", 150, 10, 33),
    ("300x12", 300, 12, 55),
]
CPSAT_LIMIT = 60.0
GA_LIMIT = 30.0
GA_RUNS = 3


def load_progress() -> dict:
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(data: dict):
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def plot_convergence(all_hist: dict):
    plt.figure(figsize=(8, 5))
    for name, hist in all_hist.items():
        plt.plot(hist, label=name, lw=1.2)
    plt.xlabel("generation (x5)")
    plt.ylabel("best makespan")
    plt.title("GA convergence curves")
    plt.grid(alpha=0.3)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "convergence.png"), dpi=150)
    plt.close()


def plot_gantt(inst, res, title, fname):
    fig, ax = plt.subplots(figsize=(10, 0.45 * inst.n_nodes + 1))
    cmap = plt.get_cmap("tab20")
    for i in range(inst.n_tasks):
        j = res["node"][i]
        s = res["start"][i]
        d = int(inst.duration[i, j])
        ax.barh(j, d, left=s, height=0.7, color=cmap(i % 20),
                edgecolor="white", linewidth=0.3)
    ax.set_yticks(range(inst.n_nodes))
    ax.set_yticklabels(inst.node_names, fontsize=8)
    ax.set_xlabel("time")
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(fname, dpi=150)
    plt.close()


def main():
    progress = load_progress()
    conv_data = {}
    rows = []

    for name, n, m, seed in SCALES:
        key = f"{name}_s{seed}"
        inst = generate_instance(n_tasks=n, n_nodes=m, seed=seed)

        if key in progress:
            rec = progress[key]
            print(f"[skip] {key} already done")
        else:
            print(f"[run ] {key}: CP-SAT ({CPSAT_LIMIT}s) ...")
            cpsat = solve_instance(inst, time_limit=CPSAT_LIMIT)
            print(f"[run ] {key}: GA x{GA_RUNS} ({GA_LIMIT}s each) ...")
            ga_runs = []
            for r in range(GA_RUNS):
                res = GeneticScheduler(inst, seed=100 + r).solve(
                    time_limit=GA_LIMIT)
                ga_runs.append(res)
            best = min(ga_runs, key=lambda x: x["makespan"])
            avg = int(np.mean([x["makespan"] for x in ga_runs]))
            rec = {
                "cpsat": {k: v for k, v in cpsat.items()
                          if k in ("status", "makespan", "wall_time_s")},
                "ga_best": best["makespan"],
                "ga_avg": avg,
                "ga_time_s": best["wall_time_s"],
                "baselines": {
                    row["method"]: row["makespan"]
                    for row in run_baselines(inst, seed=seed)
                },
            }
            progress[key] = rec
            save_progress(progress)
            conv_data[key] = best["history"]
            plot_gantt(inst, cpsat, f"CP-SAT makespan={cpsat['makespan']}",
                       os.path.join(OUT, f"gantt_cpsat_{name}.png"))
            plot_gantt(inst, best, f"GA makespan={best['makespan']}",
                       os.path.join(OUT, f"gantt_ga_{name}.png"))

        # Add baseline values to older experiment records without rerunning
        # expensive solver jobs.
        if "baselines" not in rec:
            rec["baselines"] = {
                row["method"]: row["makespan"]
                for row in run_baselines(inst, seed=seed)
            }
            progress[key] = rec
            save_progress(progress)

        gap = (rec["ga_best"] - rec["cpsat"]["makespan"]) / \
            rec["cpsat"]["makespan"] * 100
        rows.append({
            "scale": name,
            "cpsat_makespan": rec["cpsat"]["makespan"],
            "cpsat_status": rec["cpsat"]["status"],
            "cpsat_time_s": rec["cpsat"]["wall_time_s"],
            "greedy": rec["baselines"]["greedy_earliest_finish"],
            "lpt": rec["baselines"]["lpt"],
            "ga_best": rec["ga_best"],
            "ga_avg": rec["ga_avg"],
            "ga_time_s": rec["ga_time_s"],
            "gap_pct": round(gap, 1),
        })

    save_progress(progress)
    if conv_data:
        plot_convergence(conv_data)

    print("\n=== result table ===")
    header = f"{'scale':>8} {'cpsat':>7} {'greedy':>7} {'lpt':>7} " \
             f"{'ga_best':>8} {'gap%':>6} {'ga_t(s)':>8}"
    print(header)
    for r in rows:
        print(f"{r['scale']:>8} {r['cpsat_makespan']:>7} "
              f"{r.get('greedy', '-'):>7} {r.get('lpt', '-'):>7} "
              f"{r['ga_best']:>8} {r['gap_pct']:>6} {r['ga_time_s']:>8}")
    print(f"\ntable saved: {os.path.join(OUT, 'experiments.json')}")


if __name__ == "__main__":
    main()
