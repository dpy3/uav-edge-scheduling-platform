from fastapi.testclient import TestClient


def test_frontend_root_is_served(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert '<div id="root"></div>' in response.text


def test_frontend_route_falls_back_to_index(client: TestClient) -> None:
    response = client.get("/scheduling")

    assert response.status_code == 200
    assert '<div id="root"></div>' in response.text


def test_unknown_api_route_is_not_handled_by_frontend(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
