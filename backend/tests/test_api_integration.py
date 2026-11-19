import pytest
from fastapi.testclient import TestClient

from app import providers
from app.contracts import BURNING_T_U8
from app.main import app
from app.protocol import unpack_frame
from experiments.run import SPECS_DIR
from experiments.spec import load

# End to end with whatever providers are active (the real solver and scenes by default).


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def run_session(client, preset: str, frames: int = 30):
    meta = client.post("/api/scenes/build", json={"preset": preset, "density": 1.0, "seed": 0}).json()
    with client.websocket_connect("/ws/sim") as ws:
        ws.send_json({"type": "start", "scene_id": meta["id"], "params": {}})
        session_id = ws.receive_json()["id"]
        assert ws.receive_json()["state"] == "running"
        # Away from the firebreak strip (x = 100 m) and the river (y ≈ 100 m).
        ws.send_json({"type": "ignite", "x": 50.0, "y": 50.0})
        ws.send_json({"type": "set_speed", "speed": 5})
        last = None
        while last is None or last.frame < frames:
            msg = ws.receive()
            if msg.get("bytes"):
                last = unpack_frame(msg["bytes"])
            elif '"finished"' in (msg.get("text") or ""):
                pytest.fail(f"fire went out early in {preset}")
    return meta, session_id, last


@pytest.mark.parametrize("preset", [p["id"] for p in providers.list_presets() if not p["id"][-1].isdigit()])
def test_fire_spreads_in_every_preset(client, preset):
    meta, session_id, frame = run_session(client, preset)
    assert frame.T.shape == (meta["ny"], meta["nx"])
    assert (frame.T >= BURNING_T_U8).any(), f"nothing burning in {preset}"
    csv = client.get(f"/api/sessions/{session_id}/export.csv").text.strip().split("\n")
    assert len(csv) > 10
    assert float(csv[-1].split(",")[3]) > 0  # burned_area


def test_bundled_specs_are_valid():
    specs = sorted(SPECS_DIR.glob("*.toml"))
    assert specs
    for path in specs:
        assert load(path).runs, path.name
