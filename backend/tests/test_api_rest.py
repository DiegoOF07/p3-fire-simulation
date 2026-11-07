import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.protocol import unpack_frame


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def scene(client):
    res = client.post("/api/scenes/build", json={"preset": "flat", "density": 0.5, "seed": 1})
    assert res.status_code == 200
    return res.json()


def test_params_follow_spec(client):
    specs = client.get("/api/params").json()
    assert specs
    for s in specs:
        assert {"name", "min", "max", "default", "live"} <= s.keys()
        assert s["min"] <= s["default"] <= s["max"]


def test_presets(client):
    assert any(p["id"] == "flat" for p in client.get("/api/scenes").json())


def test_unknown_preset_is_404(client):
    assert client.post("/api/scenes/build", json={"preset": "nope"}).status_code == 404


def test_heightmap_and_trees_binary(client, scene):
    hm = client.get(f"/api/scenes/{scene['id']}/heightmap")
    assert hm.headers["content-type"] == "application/octet-stream"
    assert np.frombuffer(hm.content, "<f4").size == scene["nx"] * scene["ny"]
    trees = np.frombuffer(client.get(f"/api/scenes/{scene['id']}/trees").content, "<f4")
    assert trees.size == scene["n_trees"] * 4


def test_missing_scene_is_404(client):
    assert client.get("/api/scenes/missing/heightmap").status_code == 404


def test_ws_streams_frames(client, scene):
    with client.websocket_connect("/ws/sim") as ws:
        ws.send_json({"type": "start", "scene_id": scene["id"], "params": {}})
        assert ws.receive_json()["type"] == "session"
        assert ws.receive_json() == {"type": "state", "state": "running", "speed": 1}
        ws.send_json({"type": "ignite", "x": 100, "y": 100})
        frames = []
        while len(frames) < 3:
            msg = ws.receive()
            if msg.get("bytes"):
                frames.append(unpack_frame(msg["bytes"]))
        assert [f.frame for f in frames] == [1, 2, 3]
        assert frames[0].T.shape == (scene["ny"], scene["nx"])


def test_ws_rejects_unknown_scene(client):
    with client.websocket_connect("/ws/sim") as ws:
        ws.send_json({"type": "start", "scene_id": "missing"})
        assert ws.receive_json()["type"] == "error"


def test_scene_meta(client, scene):
    assert client.get(f"/api/scenes/{scene['id']}").json() == scene
    assert client.get("/api/scenes/missing").status_code == 404


def test_export_csv(client, scene):
    with client.websocket_connect("/ws/sim") as ws:
        ws.send_json({"type": "start", "scene_id": scene["id"], "params": {}})
        session_id = ws.receive_json()["id"]
        ws.send_json({"type": "ignite", "x": 100, "y": 100})
        frames = 0
        while frames < 3:
            if ws.receive().get("bytes"):
                frames += 1
    res = client.get(f"/api/sessions/{session_id}/export.csv")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert f"session-{session_id}.csv" in res.headers["content-disposition"]
    header, *rows = res.text.strip().split("\n")
    assert header == "frame,t,burned_area,burned_trees,front_speed,T_max"
    assert len(rows) >= 3
    assert rows[0].startswith("1,")


def test_export_unknown_session_is_404(client):
    assert client.get("/api/sessions/missing/export.csv").status_code == 404
