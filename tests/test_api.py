from pathlib import Path

from fastapi.testclient import TestClient

from routemate.api import create_app
from routemate.config import Settings


def test_health_and_chat_in_offline_mode(tmp_path: Path) -> None:
    app = create_app(Settings(mode="offline", output_dir=tmp_path))

    with TestClient(app) as client:
        health = client.get("/health")
        response = client.post(
            "/v1/chat",
            json={"message": "查询杭州天气", "thread_id": "api-test"},
        )

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "mode": "offline"}
    assert response.status_code == 200
    assert response.json()["mode"] == "offline"
    assert response.json()["tool_calls"][0]["name"] == "query_weather_demo"


def test_chat_validates_thread_id(tmp_path: Path) -> None:
    app = create_app(Settings(mode="offline", output_dir=tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat",
            json={"message": "查询北京天气", "thread_id": "bad thread"},
        )

    assert response.status_code == 400
    assert "thread_id" in response.json()["detail"]

