"""HTTP API for the UAV-edge scheduling prototype.

The service deliberately keeps instance generation and solving stateless. This
makes it easy to embed the solver in a larger FastAPI/PostgreSQL application
later without coupling the optimization code to a web framework.
"""
from __future__ import annotations

from typing import Any, Literal

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from baselines import greedy_earliest_finish, lpt_schedule
from problem import generate_instance, instance_from_specs
from solve_cpsat import solve_instance
from solve_ga import GeneticScheduler


Method = Literal["greedy", "lpt", "ga", "cpsat", "business"]


class EdgeTask(BaseModel):
    task_id: int | None = None
    workload_mcycles: float = Field(ge=1, le=1_000_000)
    data_size_mb: float = Field(default=0, ge=0, le=100_000)
    release_time: int = Field(default=0, ge=0)
    deadline: int | None = Field(default=None, ge=0)
    priority: int = Field(default=1, ge=1, le=10)


class EdgeNode(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    compute_capacity: float = Field(ge=0.1, le=1_000_000)
    bandwidth_mbps: float = Field(default=1, gt=0, le=1_000_000)


class SchedulingScenario(BaseModel):
    tasks: list[EdgeTask] = Field(min_length=1, max_length=300)
    nodes: list[EdgeNode] = Field(min_length=1, max_length=32)
    source_name: str = "generated"


class ScheduleRequest(BaseModel):
    n_tasks: int = Field(default=20, ge=1, le=300)
    n_nodes: int = Field(default=4, ge=1, le=32)
    seed: int = Field(default=42, ge=0)
    method: Method = "greedy"
    time_limit: float = Field(default=5.0, gt=0, le=60)
    scenario: SchedulingScenario | None = None


class ScheduleTask(BaseModel):
    task_id: int
    node_id: int
    node_name: str
    release_time: int
    start_time: int
    duration: int
    end_time: int
    priority: int
    data_size_mb: float
    deadline: int
    workload_mcycles: float


class ScheduleResponse(BaseModel):
    method: str
    status: str
    makespan: int
    wall_time_s: float
    n_tasks: int
    n_nodes: int
    seed: int
    tasks: list[ScheduleTask]
    nodes: list[EdgeNode]
    source_name: str


app = FastAPI(
    title="UAV Edge Scheduling API",
    version="0.1.0",
    description="Stateless scheduling service for reproducible UAV-edge instances.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _solve(request: ScheduleRequest):
    instance = (
        instance_from_specs(
            [task.model_dump(exclude_none=True) for task in request.scenario.tasks],
            [node.model_dump() for node in request.scenario.nodes],
        )
        if request.scenario
        else generate_instance(
            n_tasks=request.n_tasks,
            n_nodes=request.n_nodes,
            seed=request.seed,
        )
    )
    if request.method == "greedy":
        return instance, greedy_earliest_finish(instance)
    if request.method == "lpt":
        return instance, lpt_schedule(instance)
    if request.method == "business":
        from baselines import business_aware_schedule
        return instance, business_aware_schedule(instance)
    if request.method == "ga":
        return instance, GeneticScheduler(instance, seed=request.seed).solve(
            time_limit=request.time_limit,
        )
    return instance, solve_instance(
        instance,
        time_limit=request.time_limit,
        num_workers=1,
    )


@app.post("/schedule", response_model=ScheduleResponse)
def schedule(request: ScheduleRequest) -> ScheduleResponse:
    try:
        instance, result = _solve(request)
    except (IndexError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    node_ids = np.asarray(result["node"], dtype=int)
    starts = np.asarray(result["start"], dtype=int)
    tasks = [
        ScheduleTask(
            task_id=int(instance.task_metadata[i]["task_id"]),
            node_id=int(node_ids[i]),
            node_name=instance.node_names[int(node_ids[i])],
            release_time=int(instance.release[i]),
            start_time=int(starts[i]),
            duration=int(instance.duration[i, node_ids[i]]),
            end_time=int(starts[i] + instance.duration[i, node_ids[i]]),
            priority=int(instance.task_metadata[i]["priority"]),
            data_size_mb=float(instance.task_metadata[i]["data_size_mb"]),
            deadline=int(instance.task_metadata[i]["deadline"]),
            workload_mcycles=float(instance.task_metadata[i]["workload_mcycles"]),
        )
        for i in range(instance.n_tasks)
    ]
    status = str(result.get("status", "HEURISTIC"))
    return ScheduleResponse(
        method=request.method,
        status=status,
        makespan=int(result["makespan"]),
        wall_time_s=float(result["wall_time_s"]),
        n_tasks=instance.n_tasks,
        n_nodes=instance.n_nodes,
        seed=request.seed,
        tasks=tasks,
        nodes=[
            EdgeNode(
                name=instance.node_names[i],
                compute_capacity=instance.node_capacities[i],
                bandwidth_mbps=instance.node_bandwidths[i],
            )
            for i in range(instance.n_nodes)
        ],
        source_name=request.scenario.source_name if request.scenario else "generated",
    )
