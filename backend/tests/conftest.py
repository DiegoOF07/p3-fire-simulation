import pytest

from app import providers
from app.mock import scenes as mock_scenes
from app.mock import simulation as mock_sim

# These API tests check session/protocol behaviour with the mock's known numbers
# (dt = 0.5 s, spread_speed), whatever implementation is the default.
MOCK_PINNED = {
    "test_api_experiments",
    "test_api_mock",
    "test_api_rest",
    "test_api_session",
    "test_api_ws",
}


@pytest.fixture(autouse=True)
def pin_mock_providers(request, monkeypatch):
    if request.module.__name__.rsplit(".", 1)[-1] not in MOCK_PINNED:
        return
    monkeypatch.setattr(providers, "list_presets", mock_scenes.list_presets)
    monkeypatch.setattr(providers, "build_scene", mock_scenes.build_scene)
    monkeypatch.setattr(providers, "param_specs", mock_sim.param_specs)
    monkeypatch.setattr(providers, "create_simulation", mock_sim.create_simulation)
    monkeypatch.setattr(providers, "BASE_STEPS", 1)
