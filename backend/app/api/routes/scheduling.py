"""Authenticated business adapter for the UAV-edge scheduling service."""

import csv
import io
import json
import uuid
from typing import Literal

import httpx
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, ValidationError
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.models import SchedulingRun, SchedulingRunPublic, SchedulingRunsPublic

router = APIRouter(prefix="/scheduling", tags=["scheduling"])

SchedulingMethod = Literal["greedy", "lpt", "ga", "cpsat", "business"]


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


class ComparisonRequest(BaseModel):
    n_tasks: int = Field(default=20, ge=1, le=300)
    n_nodes: int = Field(default=4, ge=1, le=32)
    seed: int = Field(default=42, ge=0)
    methods: list[SchedulingMethod] = Field(
        default=["greedy", "lpt", "ga", "cpsat", "business"], min_length=2, max_length=5
    )
    time_limit: float = Field(default=5.0, gt=0, le=60)
    scenario: SchedulingScenario | None = None


class ScenarioImportResponse(SchedulingScenario):
    pass


class SchedulingRunRequest(BaseModel):
    n_tasks: int = Field(default=20, ge=1, le=300)
    n_nodes: int = Field(default=4, ge=1, le=32)
    seed: int = Field(default=42, ge=0)
    method: SchedulingMethod = "greedy"
    time_limit: float = Field(default=5.0, gt=0, le=60)
    scenario: SchedulingScenario | None = None


class SchedulingRunResponse(SchedulingRunPublic):
    pass


def _run_payload(request: SchedulingRunRequest) -> dict[str, object]:
    return request.model_dump(exclude_none=True)


async def _call_solver(payload: dict[str, object], timeout: float) -> dict[str, object]:
    url = f"{str(settings.SCHEDULER_SERVICE_URL).rstrip('/')}/schedule"
    try:
        async with httpx.AsyncClient(timeout=timeout + 5) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except httpx.ConnectError as exc:
        raise HTTPException(status_code=503, detail="Scheduling service is unavailable") from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Scheduling service timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="Scheduling service returned an error") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Could not reach scheduling service") from exc
    return response.json()


def _persist_run(
    solver_payload: dict[str, object], request: SchedulingRunRequest,
    session: SessionDep, current_user: CurrentUser,
) -> SchedulingRunResponse:
    run_id = uuid.uuid4()
    solver_result = SchedulingRunResponse.model_validate(
        {**solver_payload, "id": run_id, "owner_id": current_user.id,
         "time_limit": request.time_limit, "created_at": None}
    )
    run = SchedulingRun(
        id=run_id, owner_id=current_user.id, method=solver_result.method,
        status=solver_result.status, n_tasks=solver_result.n_tasks,
        n_nodes=solver_result.n_nodes, seed=solver_result.seed,
        time_limit=request.time_limit, makespan=solver_result.makespan,
        wall_time_s=solver_result.wall_time_s, result_json=solver_payload,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    solver_result.created_at = run.created_at
    return solver_result


@router.post("/runs", response_model=SchedulingRunResponse)
async def create_scheduling_run(
    request: SchedulingRunRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> SchedulingRunResponse:
    """Submit one scheduling run to the optimization service.

    Authentication stays in the platform API while the stateless solver remains
    independently deployable and replaceable.
    """
    solver_payload = await _call_solver(_run_payload(request), request.time_limit)
    return _persist_run(solver_payload, request, session, current_user)


@router.post("/compare", response_model=list[SchedulingRunResponse])
async def compare_scheduling_methods(
    request: ComparisonRequest, session: SessionDep, current_user: CurrentUser,
) -> list[SchedulingRunResponse]:
    """Run selected methods against exactly the same UAV-edge scenario."""
    results = []
    for method in dict.fromkeys(request.methods):
        run_request = SchedulingRunRequest(
            n_tasks=request.n_tasks, n_nodes=request.n_nodes, seed=request.seed,
            method=method, time_limit=request.time_limit, scenario=request.scenario,
        )
        payload = await _call_solver(_run_payload(run_request), run_request.time_limit)
        results.append(_persist_run(payload, run_request, session, current_user))
    return results


@router.post("/import", response_model=ScenarioImportResponse)
async def import_scenario(
    current_user: CurrentUser, file: UploadFile = File(...)
) -> ScenarioImportResponse:
    """Parse a scenario from JSON or a two-section CSV file without persisting it."""
    del current_user
    filename = file.filename or "scenario"
    try:
        raw = (await file.read()).decode("utf-8-sig")
        if filename.lower().endswith(".json"):
            payload = json.loads(raw)
            return ScenarioImportResponse.model_validate(payload)
        rows = list(csv.DictReader(io.StringIO(raw)))
        if not rows or "record_type" not in rows[0]:
            raise ValueError("CSV must contain a record_type column")
        tasks = [
            EdgeTask.model_validate(row) for row in rows if row["record_type"].lower() == "task"
        ]
        nodes = [
            EdgeNode.model_validate(row) for row in rows if row["record_type"].lower() == "node"
        ]
        return ScenarioImportResponse(tasks=tasks, nodes=nodes, source_name=filename)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid scenario file: {exc}") from exc


@router.get("/runs", response_model=SchedulingRunsPublic)
def read_scheduling_runs(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> SchedulingRunsPublic:
    """List the current user's persisted scheduling runs."""
    count = session.exec(
        select(func.count())
        .select_from(SchedulingRun)
        .where(SchedulingRun.owner_id == current_user.id)
    ).one()
    runs = session.exec(
        select(SchedulingRun)
        .where(SchedulingRun.owner_id == current_user.id)
        .order_by(col(SchedulingRun.created_at).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    data = [
        SchedulingRunPublic(
            id=run.id,
            owner_id=run.owner_id,
            method=run.method,
            status=run.status,
            n_tasks=run.n_tasks,
            n_nodes=run.n_nodes,
            seed=run.seed,
            time_limit=run.time_limit,
            makespan=run.makespan,
            wall_time_s=run.wall_time_s,
            tasks=run.result_json.get("tasks", []),
            nodes=run.result_json.get("nodes", []),
            source_name=run.result_json.get("source_name", "generated"),
            created_at=run.created_at,
        )
        for run in runs
    ]
    return SchedulingRunsPublic(data=data, count=count)
