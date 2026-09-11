from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.api.routes import scheduling
from app.core.config import settings


class FakeAsyncClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, json: dict) -> httpx.Response:
        assert url.endswith("/schedule")
        payload = self.response.json()
        payload.setdefault("method", json["method"])
        return httpx.Response(
            status_code=self.response.status_code,
            json=payload,
            request=self.response.request,
        )


def test_create_scheduling_run(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch,
) -> None:
    payload = {
        "method": "greedy",
        "status": "HEURISTIC",
        "makespan": 272,
        "wall_time_s": 0.01,
        "n_tasks": 8,
        "n_nodes": 3,
        "seed": 7,
        "tasks": [],
        "nodes": [],
        "source_name": "generated",
    }
    response = httpx.Response(
        status_code=200,
        json=payload,
        request=httpx.Request("POST", "http://scheduler-api:8000/schedule"),
    )
    monkeypatch.setattr(
        scheduling.httpx,
        "AsyncClient",
        lambda **_: FakeAsyncClient(response),
    )

    result = client.post(
        f"{settings.API_V1_STR}/scheduling/runs",
        headers=superuser_token_headers,
        json={"n_tasks": 8, "n_nodes": 3, "seed": 7, "method": "greedy"},
    )

    assert result.status_code == 200
    assert result.json()["makespan"] == 272


def test_compare_scheduling_methods_persists_each_result(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch,
) -> None:
    payload = {
        "status": "HEURISTIC", "makespan": 100, "wall_time_s": 0.01,
        "n_tasks": 3, "n_nodes": 2, "seed": 7, "tasks": [], "nodes": [],
        "source_name": "generated",
    }

    def fake_client(**_: object) -> FakeAsyncClient:
        return FakeAsyncClient(httpx.Response(
            status_code=200, json=payload,
            request=httpx.Request("POST", "http://scheduler-api:8000/schedule"),
        ))

    monkeypatch.setattr(scheduling.httpx, "AsyncClient", fake_client)
    result = client.post(
        f"{settings.API_V1_STR}/scheduling/compare",
        headers=superuser_token_headers,
        json={"n_tasks": 3, "n_nodes": 2, "seed": 7, "methods": ["greedy", "lpt"]},
    )

    assert result.status_code == 200
    assert [run["method"] for run in result.json()] == ["greedy", "lpt"]


def test_compare_accepts_business_aware_method(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch,
) -> None:
    payload = {
        "status": "HEURISTIC", "makespan": 100, "wall_time_s": 0.01,
        "n_tasks": 3, "n_nodes": 2, "seed": 7, "tasks": [], "nodes": [],
        "source_name": "generated",
    }

    def fake_client(**_: object) -> FakeAsyncClient:
        return FakeAsyncClient(httpx.Response(
            status_code=200, json=payload,
            request=httpx.Request("POST", "http://scheduler-api:8000/schedule"),
        ))

    monkeypatch.setattr(scheduling.httpx, "AsyncClient", fake_client)
    result = client.post(
        f"{settings.API_V1_STR}/scheduling/compare",
        headers=superuser_token_headers,
        json={"n_tasks": 3, "n_nodes": 2, "seed": 7, "methods": ["greedy", "business"]},
    )

    assert result.status_code == 200
    assert [run["method"] for run in result.json()] == ["greedy", "business"]


def test_import_json_scenario(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    scenario = {
        "source_name": "field-trial.json",
        "tasks": [{"workload_mcycles": 120, "data_size_mb": 12, "priority": 3}],
        "nodes": [{"name": "uav-local", "compute_capacity": 2, "bandwidth_mbps": 1}],
    }

    result = client.post(
        f"{settings.API_V1_STR}/scheduling/import",
        headers=superuser_token_headers,
        files={"file": ("scenario.json", __import__("json").dumps(scenario), "application/json")},
    )

    assert result.status_code == 200
    assert result.json()["tasks"][0]["priority"] == 3


def test_create_scheduling_run_requires_auth(client: TestClient) -> None:
    result = client.post(
        f"{settings.API_V1_STR}/scheduling/runs",
        json={"method": "greedy"},
    )

    assert result.status_code == 401
