import pytest
import requests

from tools import base


class FakeResponse:
    def __init__(self, status=200, payload=None, bad_json=False):
        self.status_code = status
        self._payload = payload
        self._bad_json = bad_json
        self.from_cache = False

    def json(self):
        if self._bad_json:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    """Returns the queued responses one by one; an Exception in the queue is raised."""

    def __init__(self, queue):
        self.queue, self.calls = list(queue), 0

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls += 1
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(base.time, "sleep", lambda s: None)  # keep tests fast


def use(monkeypatch, queue):
    session = FakeSession(queue)
    monkeypatch.setattr(base, "_SESSION", session)
    return session


def test_returns_json_on_success(monkeypatch):
    use(monkeypatch, [FakeResponse(200, {"a": 1})])
    assert base.get_json("http://x") == {"a": 1}


def test_retries_on_server_error_then_succeeds(monkeypatch):
    s = use(monkeypatch, [FakeResponse(503), FakeResponse(429), FakeResponse(200, {"ok": True})])
    assert base.get_json("http://x") == {"ok": True}
    assert s.calls == 3


def test_fails_fast_on_client_error(monkeypatch):
    s = use(monkeypatch, [FakeResponse(404)])
    with pytest.raises(base.ToolError, match="HTTP 404"):
        base.get_json("http://x")
    assert s.calls == 1  # no retry on 4xx


def test_gives_up_after_retries(monkeypatch):
    s = use(monkeypatch, [FakeResponse(500)] * 3)
    with pytest.raises(base.ToolError, match="request failed"):
        base.get_json("http://x")
    assert s.calls == 3


def test_network_error_is_retried(monkeypatch):
    use(monkeypatch, [requests.ConnectionError("down"), FakeResponse(200, {"ok": 1})])
    assert base.get_json("http://x") == {"ok": 1}


def test_non_json_body_raises_tool_error(monkeypatch):
    use(monkeypatch, [FakeResponse(200, bad_json=True)])
    with pytest.raises(base.ToolError, match="not JSON"):
        base.get_json("http://x")