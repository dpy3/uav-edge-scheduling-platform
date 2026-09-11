# UAV-Edge Scheduling：无人机群-边缘计算任务调度算法研究仓库

基于开源精确求解器 [PyJobShop](https://github.com/PyJobShop/PyJobShop)（OR-Tools CP-SAT 封装，MIT 协议）二次开发，
研究无人机群任务计算卸载到异构边缘节点的调度优化问题。

## 问题背景

无人机执行任务时产生若干计算密集型任务（目标识别、航迹规划、传感器数据融合等），
可卸载到异构计算节点执行：

- 节点 0：无人机本地计算单元（无传输开销、算力低）
- 节点 1..M-1：边缘服务器（算力高、需计入上行传输时间）

目标：最小化 **makespan**（全部任务完成时刻）。
该问题等价于调度理论中的 **Rm | r_j | Cmax**，属于 NP-hard，
既可用约束规划精确求解（中小规模），也适合元启发式算法（大规模）。

## 项目结构与我的贡献

| 文件 | 内容 |
|---|---|
| `problem.py` | 问题建模与可复现随机实例生成器（计算量/算力/传输延迟/释放时间） |
| `solve_cpsat.py` | 精确求解基线：PyJobShop 建模（job=任务、machine=节点、mode=节点上的加工） |
| `solve_ga.py` | 自实现混合遗传算法：双段染色体（节点分配+任务顺序）、OX 交叉、memetic 局部搜索 |
| `baselines.py` | 随机、最早完成时间、LPT 三类轻量基线 |
| `metrics.py` | gap、均值、标准差等统一指标 |
| `run_experiments.py` | 多规模对比实验，输出量化结果表、收敛曲线、甘特图 |
| `tests/` | 实例生成、解码器、基线和指标测试 |

（原求解器以依赖方式安装，未修改上游源码。）

## 使用方法

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ../PyJobShop pillow matplotlib
.venv\Scripts\python.exe run_experiments.py
```

如果直接复用上级目录的 PyJobShop 环境，可执行：

```bash
..\PyJobShop\.venv\Scripts\python.exe -m pytest -q
```

## 调度 API

项目提供一个无状态 FastAPI 服务，当前支持 `greedy`、`lpt`、`ga` 和
`cpsat` 四种求解方式。先安装 API 依赖：

```bash
..\PyJobShop\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
..\PyJobShop\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8001
```

然后访问 `http://127.0.0.1:8001/docs` 查看 OpenAPI 文档，或发送请求：

```bash
curl -X POST http://127.0.0.1:8001/schedule \
  -H "Content-Type: application/json" \
  -d '{"n_tasks":20,"n_nodes":4,"seed":11,"method":"greedy"}'
```

返回结果包含每个任务的节点、释放时间、开始时间、持续时间和结束时间，
后续可以直接接入 PostgreSQL 运行记录和前端甘特图。

## 实验结果（CP-SAT vs 混合 GA）

| 规模 | CP-SAT | 贪心 | LPT | GA best | GA avg | GA gap % |
|---|---|---|---|---|---|---|
| 20x4 | 284 | 308 | 375 | 295 | 308 | 3.9% |
| 40x5 | 559* | 606 | 696 | 652 | 669 | 16.6% |
| 80x8 | 526* | 572 | 642 | 649 | 676 | 23.4% |
| 150x10 | 777* | 799 | 990 | 1057 | 1077 | 36.0% |
| 300x12 | 1235* | 1266 | 1584 | 1714 | 1791 | 38.8% |

`*` 表示 CP-SAT 在 60 秒限制内返回可行解（`FEASIBLE`），不是已证明的最优解。
当前结果说明：GA 在最小规模接近精确基线，但大规模仍落后于贪心基线；后续工作应优先改进初始化、邻域搜索和多目标建模，不能把当前结果表述为 GA 已经全面优于基线。

图表见 `results/`：`convergence.png`（GA 收敛曲线）、`gantt_*.png`（调度甘特图）。

完整原始结果见 `results/experiments.json`，每次实验使用固定随机种子并增量写盘。

## 后续工作

详细实验状态见 [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)。

- [x] 增加随机、贪心和 LPT 基线并记录运行结果
- [x] 增加实例、解码器、基线和指标测试
- [ ] 大规模实例下 CP-SAT、基线与 GA 的求解时间-质量权衡分析
- [ ] 引入任务间依赖（DAG 约束）建模多阶段计算流水线
- [ ] 与论文实验章节对齐：多目标（能耗 + 时延）扩展

## 简历项目边界

本项目不是简单调用开源求解器：`problem.py`、`baselines.py`、`solve_ga.py`、
`metrics.py` 和 API 服务为本项目新增代码；PyJobShop 作为 MIT 协议依赖，负责
CP-SAT 建模与求解。简历中应如实描述当前结果，重点突出问题建模、基线对比、
遗传算法实现、可复现实验和服务化接口。

## 许可说明

本项目调度求解部分依赖 PyJobShop（MIT 协议，原项目见上方链接），
本仓库新增代码为作者独立贡献。
