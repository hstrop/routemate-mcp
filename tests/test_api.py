from pathlib import Path

from fastapi.testclient import TestClient

from routemate.api import create_app
from routemate.config import Settings


def test_health_and_chat_in_offline_mode(tmp_path: Path) -> None:
    app = create_app(Settings(mode="offline", output_dir=tmp_path))

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/meta").json()["name"] == "RouteMate"
        health = client.get("/health")
        response = client.post(
            "/v1/chat",
            json={"message": "查询杭州天气", "thread_id": "api-test"},
        )
        reset = client.post("/v1/threads/api-test/reset")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "mode": "offline", "started": True}
    assert response.status_code == 200
    assert response.json()["mode"] == "offline"
    assert response.json()["tool_calls"][0]["name"] == "query_weather_demo"

    assert reset.status_code == 200
    assert reset.json()["reset"] is True


def test_chat_validates_thread_id(tmp_path: Path) -> None:
    app = create_app(Settings(mode="offline", output_dir=tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat",
            json={"message": "查询北京天气", "thread_id": "bad thread"},
        )

    assert response.status_code == 400
    assert "thread_id" in response.json()["detail"]


def test_offline_route_demo_is_a_tool_trace(tmp_path: Path) -> None:
    app = create_app(Settings(mode="offline", output_dir=tmp_path))
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat",
            json={"message": "从广州到深圳怎么走？", "thread_id": "route-demo"},
        )
    assert response.status_code == 200
    assert response.json()["tool_calls"][0]["name"] == "plan_route_demo"
    assert "137" in response.json()["answer"]
