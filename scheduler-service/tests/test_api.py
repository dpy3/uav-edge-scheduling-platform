from __future__ import annotations

from fastapi.testclient import TestClient

from api import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_schedule_endpoint_returns_task_records():
    response = client.post(
        "/schedule",
        json={"n_tasks": 8, "n_nodes": 3, "seed": 11, "method": "greedy"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["method"] == "greedy"
    assert body["n_tasks"] == 8
    assert body["makespan"] > 0
    assert len(body["tasks"]) == 8
    assert all(task["end_time"] >= task["start_time"] for task in body["tasks"])


def test_schedule_rejects_out_of_range_request():
    response = client.post("/schedule", json={"n_tasks": 0})
    assert response.status_code == 422


def test_schedule_uses_imported_uav_edge_scenario():
    response = client.post(
        "/schedule",
        json={
            "method": "greedy",
            "scenario": {
                "source_name": "field-trial.json",
                "tasks": [
                    {"task_id": 9, "workload_mcycles": 40, "data_size_mb": 8,
                     "release_time": 2, "deadline": 30, "priority": 5}
                ],
                "nodes": [
                    {"name": "uav-local", "compute_capacity": 2, "bandwidth_mbps": 1},
                    {"name": "edge-a", "compute_capacity": 10, "bandwidth_mbps": 20},
                ],
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_name"] == "field-trial.json"
    assert body["tasks"][0]["priority"] == 5
    assert body["tasks"][0]["data_size_mb"] == 8
    assert body["nodes"][1]["compute_capacity"] == 10


def test_schedule_accepts_imported_uav_edge_scenario():
    response = client.post(
        "/schedule",
        json={
            "method": "greedy",
            "scenario": {
                "source_name": "demo-uav.json",
                "nodes": [
                    {"name": "UAV-local", "compute_capacity": 2, "bandwidth_mbps": 100},
                    {"name": "edge-a", "compute_capacity": 10, "bandwidth_mbps": 20},
                ],
                "tasks": [
                    {"task_id": 0, "workload_mcycles": 100, "data_size_mb": 20, "release_time": 0, "deadline": 30, "priority": 5},
                    {"task_id": 1, "workload_mcycles": 60, "data_size_mb": 8, "release_time": 2, "deadline": 25, "priority": 2},
                ],
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_name"] == "demo-uav.json"
    assert body["n_tasks"] == 2
    assert body["nodes"][1]["compute_capacity"] == 10
    assert body["tasks"][0]["priority"] == 5
    assert body["tasks"][0]["data_size_mb"] == 20
