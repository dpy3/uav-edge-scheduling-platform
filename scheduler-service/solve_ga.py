"""元启发式求解：混合遗传算法（GA + 局部搜索）求解同一调度实例。

编码设计（双段染色体）：
  - 段 1 assign[i] : 任务 i 卸载到的节点编号（整数编码）
  - 段 2 order     : 任务解码顺序（排列编码，OX 交叉）
解码：按 order 顺序贪心放置，start = max(节点空闲时刻, 释放时间)。

改进点（相对标准 GA，论文/简历可讲）：
  - 精英保留 + 锦标赛选择；
  - 变异包含"节点重分配"与"顺序交换"两种算子；
  - 每隔若干代对当代最优个体做一次局部搜索：
    将完工最晚的任务尝试迁移到其它节点，接受改进解（memetic 思想）。
"""
from __future__ import annotations

import time

import numpy as np

from problem import Instance, generate_instance, makespan_of


class GeneticScheduler:
    def __init__(self, inst: Instance, seed: int = 0):
        self.inst = inst
        self.rng = np.random.default_rng(seed)
        self.n = inst.n_tasks
        self.m = inst.n_nodes

    # ---------- 编解码 ----------
    def _decode(self, assign: np.ndarray, order: np.ndarray) -> int:
        mk, _, _ = makespan_of(assign, order, self.inst)
        return mk

    def _random_indiv(self):
        assign = self.rng.integers(0, self.m, size=self.n)
        order = self.rng.permutation(self.n)
        return assign, order

    # ---------- 算子 ----------
    def _crossover(self, a1, a2):
        # 段1：均匀交叉
        mask = self.rng.random(self.n) < 0.5
        c_assign = np.where(mask, a1[0], a2[0])
        # 段2：OX 顺序交叉
        lo, hi = sorted(self.rng.choice(self.n, 2, replace=False))
        child = np.full(self.n, -1)
        child[lo:hi] = a1[1][lo:hi]
        fill = [x for x in a2[1] if x not in child[lo:hi]]
        idx = list(range(0, lo)) + list(range(hi, self.n))
        for pos, val in zip(idx, fill):
            child[pos] = val
        return c_assign, child

    def _mutate(self, assign, order, p=0.15):
        assign = assign.copy()
        order = order.copy()
        hit = self.rng.random(self.n) < p
        assign[hit] = self.rng.integers(0, self.m, size=hit.sum())
        if self.rng.random() < 0.5:
            i, j = self.rng.choice(self.n, 2, replace=False)
            order[i], order[j] = order[j], order[i]
        return assign, order

    def _local_search(self, assign, order, trials: int = 60):
        """对完工最晚任务做节点迁移尝试。"""
        best_mk = self._decode(assign, order)
        _, start, _ = makespan_of(assign, order, self.inst)
        end = start + self.inst.duration[np.arange(self.n), assign]
        candidates = np.argsort(-end)[:trials]
        for i in candidates:
            cur = assign[i]
            for j in range(self.m):
                if j == cur:
                    continue
                assign[i] = j
                mk = self._decode(assign, order)
                if mk < best_mk:
                    best_mk = mk
                    cur = j
                else:
                    assign[i] = cur
        return assign, best_mk

    # ---------- 主流程 ----------
    def solve(self, pop_size: int = 80, time_limit: float = 30.0,
              elite: int = 4, ls_every: int = 5) -> dict:
        rng = self.rng
        pop = [self._random_indiv() for _ in range(pop_size)]
        fits = np.array([self._decode(a, o) for a, o in pop])
        best_idx = int(np.argmin(fits))
        best = (pop[best_idx][0].copy(), pop[best_idx][1].copy())
        best_mk = int(fits[best_idx])
        history = [best_mk]

        t0 = time.perf_counter()
        gen = 0
        while time.perf_counter() - t0 < time_limit:
            gen += 1
            new_pop = [(best[0].copy(), best[1].copy())]
            while len(new_pop) < elite:
                new_pop.append((best[0].copy(), best[1].copy()))
            while len(new_pop) < pop_size:
                # 锦标赛选择
                def pick():
                    idx = rng.choice(len(pop), 3, replace=False)
                    k = idx[np.argmin(fits[idx])]
                    return pop[k]
                child = self._crossover(pick(), pick())
                child = self._mutate(*child)
                new_pop.append(child)

            pop = new_pop
            fits = np.array([self._decode(a, o) for a, o in pop])

            if gen % ls_every == 0:
                k = int(np.argmin(fits))
                a_ls, mk_ls = self._local_search(pop[k][0], pop[k][1])
                pop[k] = (a_ls, pop[k][1])
                fits[k] = mk_ls

            k = int(np.argmin(fits))
            if fits[k] < best_mk:
                best_mk = int(fits[k])
                best = (pop[k][0].copy(), pop[k][1].copy())
            history.append(best_mk)

        elapsed = time.perf_counter() - t0
        mk, start, node = makespan_of(best[0], best[1], self.inst)
        return {
            "makespan": int(best_mk),
            "wall_time_s": round(elapsed, 2),
            "generations": gen,
            "history": history,
            "start": start.tolist(),
            "node": node.tolist(),
        }


if __name__ == "__main__":
    inst = generate_instance(n_tasks=40, n_nodes=5, seed=7)
    res = GeneticScheduler(inst, seed=1).solve(time_limit=30)
    print({"makespan": res["makespan"], "time": res["wall_time_s"],
           "generations": res["generations"]})
