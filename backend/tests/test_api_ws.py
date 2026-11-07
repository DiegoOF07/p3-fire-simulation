import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.protocol import unpack_frame


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def scene_id(client):
    return client.post("/api/scenes/build", json={"preset": "flat", "density": 0.5}).json()["id"]


def next_json(ws, kind):
    while True:
        msg = ws.receive()
        if msg.get("text"):
            data = json.loads(msg["text"])
            if data["type"] == kind:
                return data


def next_frame(ws):
    while True:
        msg = ws.receive()
        if msg.get("bytes"):
            return unpack_frame(msg["bytes"])


def start(ws, scene_id):
    ws.send_json({"type": "start", "scene_id": scene_id, "params": {}})
    session = next_json(ws, "session")
    next_json(ws, "state")
    return session["id"]


def test_pause_resume_and_speed(client, scene_id):
    with client.websocket_connect("/ws/sim") as ws:
        start(ws, scene_id)
        ws.send_json({"type": "pause"})
        assert next_json(ws, "state")["state"] == "paused"
        ws.send_json({"type": "set_speed", "speed": 20})
        assert next_json(ws, "state") == {"type": "state", "state": "paused", "speed": 20}
        ws.send_json({"type": "resume"})
        assert next_json(ws, "state")["state"] == "running"
        a, b = next_frame(ws), next_frame(ws)
        assert b.t - a.t == pytest.approx(20 * 0.5)


def test_ignite_while_paused_sends_a_frame(client, scene_id):
    with client.websocket_connect("/ws/sim") as ws:
        start(ws, scene_id)
        ws.send_json({"type": "pause"})
        next_json(ws, "state")
        ws.send_json({"type": "ignite", "x": 100, "y": 100})
        while True:
            metrics = next_json(ws, "metrics")["metrics"]
            if metrics["burned_area"] > 0:
                break


def test_reset_creates_new_session(client, scene_id):
    with client.websocket_connect("/ws/sim") as ws:
        first = start(ws, scene_id)
        ws.send_json({"type": "reset"})
        assert next_json(ws, "session")["id"] != first
        assert next_frame(ws).frame == 1


@pytest.mark.parametrize("msg, fragment", [
    ({"type": "pause"}, "start first"),
    ({"type": "start"}, "missing field"),
    ({"type": "start", "scene_id": "missing"}, "unknown scene_id"),
])
def test_errors_before_start(client, msg, fragment):
    with client.websocket_connect("/ws/sim") as ws:
        ws.send_json(msg)
        assert fragment in next_json(ws, "error")["message"]


def test_bad_messages_keep_socket_open(client, scene_id):
    with client.websocket_connect("/ws/sim") as ws:
        start(ws, scene_id)
        ws.send_text("not json")
        next_json(ws, "error")
        ws.send_json({"type": "set_param", "name": "spread_speed", "value": 999})
        assert "must be in" in next_json(ws, "error")["message"]
        ws.send_json({"type": "warp"})
        next_json(ws, "error")
        ws.send_json({"type": "pause"})
        assert next_json(ws, "state")["state"] == "paused"
