from fastapi.testclient import TestClient

from app.api import routes
from main import app


class FakeCursor:
    def __init__(self, row):
        self.row, self.calls = row, []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def execute(self, sql, args):
        self.calls.append((sql, args))
    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row):
        self.cur = FakeCursor(row)
        self.committed = False
        self.closed = False
    def cursor(self):
        return self.cur
    def commit(self):
        self.committed = True
    def close(self):
        self.closed = True


def test_enqueue_requires_exact_analysis_id():
    with TestClient(app) as client:
        response = client.post('/api/analyze-bug', json={"bug_report_id": "bug"})
    assert response.status_code == 422


def test_enqueue_uses_exact_association_and_does_not_launch_background_model(monkeypatch):
    conn = FakeConnection(("pending",))
    monkeypatch.setattr(routes, 'get_db_connection', lambda: conn)
    with TestClient(app) as client:
        response = client.post('/api/analyze-bug', json={"bug_report_id": "bug", "analysis_id": "analysis"})
    assert response.status_code == 202
    assert response.json()["analysis_id"] == "analysis"
    assert all(args == ("analysis", "bug") for _, args in conn.cur.calls)
    assert conn.committed and conn.closed


def test_enqueue_rejects_unknown_association(monkeypatch):
    conn = FakeConnection(None)
    monkeypatch.setattr(routes, 'get_db_connection', lambda: conn)
    with TestClient(app) as client:
        response = client.post('/api/analyze-bug', json={"bug_report_id": "other", "analysis_id": "analysis"})
    assert response.status_code == 404
    assert not conn.committed and conn.closed
