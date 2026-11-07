import numpy as np
import pytest

from app import providers
from app.contracts import BURNING_T_U8, METRIC_KEYS, Scene, default_params

# Checks whatever FIRE_SIM_MODULE / FIRE_SCENES_MODULE point to (mock by default).


@pytest.fixture(scope="module")
def presets():
    return providers.list_presets()


@pytest.fixture(scope="module")
def scene(presets):
    return providers.build_scene(presets[0]["id"], 0.5, 0)


def make_sim(scene):
    return providers.create_simulation(scene, default_params(providers.param_specs()))


def test_param_specs():
    specs = providers.param_specs()
    assert specs and len({s["name"] for s in specs}) == len(specs)
    for s in specs:
        assert s["min"] <= s["default"] <= s["max"], s["name"]
        assert isinstance(s["live"], bool)


def test_presets_build_valid_scenes(presets):
    assert presets and len({p["id"] for p in presets}) == len(presets)
    for p in presets:
        s = providers.build_scene(p["id"], 0.5, 0)
        assert isinstance(s, Scene)
        assert s.heightmap.dtype == np.float32 and np.isfinite(s.heightmap).all()
        assert s.trees.dtype == np.float32 and s.trees.shape[1] == 4
        x, y = s.trees[:, 0], s.trees[:, 1]
        assert ((x >= 0) & (x < s.width) & (y >= 0) & (y < s.depth)).all(), p["id"]


def test_scenes_are_deterministic(presets):
    a = providers.build_scene(presets[0]["id"], 0.5, 7)
    b = providers.build_scene(presets[0]["id"], 0.5, 7)
    np.testing.assert_array_equal(a.heightmap, b.heightmap)
    np.testing.assert_array_equal(a.trees, b.trees)


def test_unknown_preset_raises_key_error():
    with pytest.raises(KeyError):
        providers.build_scene("__nope__", 0.5, 0)


def test_density_zero_has_no_trees(presets):
    assert len(providers.build_scene(presets[0]["id"], 0.0, 0).trees) == 0


def test_idle_simulation(scene):
    sim = make_sim(scene)
    sim.step(2)
    T, beta = sim.fields_uint8()
    for field in (T, beta):
        assert field.dtype == np.uint8 and field.shape == (scene.ny, scene.nx)
        assert field.flags.c_contiguous
    assert (T < BURNING_T_U8).all()
    assert not sim.finished()
    m = sim.metrics()
    assert set(m) == set(METRIC_KEYS)
    assert m["t"] > 0 and m["burned_area"] == 0


def test_ignition_burns_and_records_history(scene):
    sim = make_sim(scene)
    sim.ignite(scene.width / 2, scene.depth / 2, 3.0)
    for _ in range(5):
        sim.step(providers.BASE_STEPS)
    T, _ = sim.fields_uint8()
    assert (T >= BURNING_T_U8).any(), "nothing burning after ignition"
    assert sim.metrics()["burned_area"] > 0
    h = sim.history()
    assert set(h) == set(METRIC_KEYS)
    assert all(len(v) == 5 for v in h.values()), "history must get one row per step() call"
    assert h["t"] == sorted(h["t"])


def test_live_params_can_change(scene):
    sim = make_sim(scene)
    for s in providers.param_specs():
        if s["live"]:
            sim.set_param(s["name"], s["max"])
    sim.step(1)
