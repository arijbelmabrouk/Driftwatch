from fastapi.testclient import TestClient

from api import main as api_main


def test_get_latest_report_returns_empty_payload_when_no_reports_exist(monkeypatch):
    monkeypatch.setattr(
        api_main,
        "_load_tracker",
        lambda tracker_id, user_id: {
            "id": tracker_id,
            "user_id": user_id,
            "topic": "test topic",
            "frequency": "weekly",
        },
    )
    monkeypatch.setattr(api_main, "load_summary", lambda topic, week: None)
    monkeypatch.setattr(api_main, "load_report", lambda topic, week_current, week_previous: None)

    app = api_main.app
    app.dependency_overrides[api_main.get_current_user] = lambda: {"id": "user-1"}

    with TestClient(app) as client:
        response = client.get("/trackers/tracker-1/report")

    assert response.status_code == 200
    assert response.json() == {
        "tracker_id": "tracker-1",
        "summary": None,
        "delta": None,
    }

    app.dependency_overrides.clear()
