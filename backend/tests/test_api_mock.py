import numpy as np

from app.contracts import BURNING_T_U8, METRIC_KEYS
from app.mock.scenes import build_scene
from app.mock.simulation import MockSimulation


def make_sim(**params):
    scene = build_scene("flat", density=1.0, seed=0)
    return scene, MockSimulation(scene, params)


def test_nothing_happens_without_ignition():
    _, sim = make_sim()
    sim.step(20)
    T, beta = sim.fields_uint8()
    assert T.max() == 0 and beta.min() == 255
    assert sim.metrics()["burned_area"] == 0
    assert not sim.finished()


def test_fire_spreads_as_a_circle():
    scene, sim = make_sim(spread_speed=2.0)
    sim.ignite(100, 100, 3)
    sim.step(20)  # 10 s -> radius ~23 m
    T, beta = sim.fields_uint8()
    assert T.dtype == np.uint8 and T.shape == (scene.ny, scene.nx)
    assert (T >= BURNING_T_U8).any()
    area = sim.metrics()["burned_area"]
    assert np.pi * 20**2 < area < np.pi * 26**2


def test_history_has_every_metric():
    _, sim = make_sim()
    sim.ignite(10, 10, 3)
    sim.step(3)
    sim.step(3)
    h = sim.history()
    assert set(h) == set(METRIC_KEYS)
    assert all(len(v) == 2 for v in h.values())


def test_finishes_once_everything_burned():
    _, sim = make_sim(spread_speed=5.0, burn_time=5.0)
    sim.ignite(100, 100, 3)
    sim.step(200)
    assert sim.finished()
