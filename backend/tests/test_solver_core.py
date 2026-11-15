import numpy as np
import pytest

from app.contracts import BURNING_T_U8, METRIC_KEYS, Scene, default_params
from app.solver import BASE_STEPS, create_simulation, param_specs
from app.solver.numerics import stable_dt

# 1D front speed with 1 m cells (analysis/02_frente_1d.ipynb).
FRONT_SPEED_1D = 0.60  # m/s


def flat_scene(n: int = 120, trees: np.ndarray | None = None) -> Scene:
    return Scene(np.zeros((n, n)), 1.0, np.zeros((0, 4)) if trees is None else trees)


def make_sim(scene: Scene, **overrides: float):
    return create_simulation(scene, default_params(param_specs()) | overrides)


def run_until(sim, t_end: float, chunk: int = 20) -> None:
    while sim.t < t_end:
        sim.step(chunk)


def test_param_specs_are_valid():
    specs = param_specs()
    assert len({s["name"] for s in specs}) == len(specs)
    for s in specs:
        assert s["min"] <= s["default"] <= s["max"], s["name"]
    live = {s["name"]: s["live"] for s in specs}
    assert live["T_inf"] is False and live["fuel"] is False


def test_nothing_happens_without_ignition():
    sim = make_sim(flat_scene(60))
    run_until(sim, 200.0)
    assert np.all(sim.T == sim.p.T_inf)
    assert np.all(sim.beta == sim.beta0)
    m = sim.metrics()
    assert m["burned_area"] == 0 and m["front_speed"] == 0
    assert not sim.finished()


def test_fire_grows_as_a_circle_on_flat_ground():
    n = 120
    sim = make_sim(flat_scene(n))
    c = n / 2
    sim.ignite(c, c, 3.0)
    run_until(sim, 50.0)
    burned = sim._burned()
    rows, cols = np.nonzero(burned)
    assert abs(rows.mean() + 0.5 - c) < 1.0 and abs(cols.mean() + 0.5 - c) < 1.0
    ci = int(c)
    reach = []
    for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]:
        k = 0
        while 0 <= ci + (k + 1) * dr < n and 0 <= ci + (k + 1) * dc < n and burned[ci + (k + 1) * dr, ci + (k + 1) * dc]:
            k += 1
        reach.append(k * np.hypot(dr, dc))
    reach = np.array(reach)
    assert reach.min() > 15, reach
    assert (reach.max() - reach.min()) / reach.mean() < 0.1, reach


def test_front_speed_matches_1d_reference():
    sim = make_sim(flat_scene(200))
    sim.ignite(100.0, 100.0, 3.0)
    run_until(sim, 120.0)
    speeds = []
    for _ in range(5):
        sim.step(BASE_STEPS * 5)
        speeds.append(sim.metrics()["front_speed"])
    assert np.mean(speeds) == pytest.approx(FRONT_SPEED_1D, rel=0.2)


def test_stable_with_extreme_live_params():
    sim = make_sim(flat_scene(60))
    for s in param_specs():
        if s["live"]:
            sim.set_param(s["name"], s["max"])
    assert sim.dt <= sim.scene.cell_size**2 / (4 * sim.p.kappa)
    sim.ignite(30.0, 30.0, 3.0)
    run_until(sim, 60.0, chunk=50)
    assert np.isfinite(sim.T).all()
    assert sim.T.max() < 5000.0
    assert (sim.beta >= 0).all() and (sim.beta <= 1).all()


def test_set_param_recomputes_dt_and_rejects_unknown():
    sim = make_sim(flat_scene(30))
    dt0 = sim.dt
    sim.set_param("kappa", 2.0)
    assert sim.dt < dt0
    assert sim.dt == pytest.approx(stable_dt(sim.p, 1.0, 1.0))
    with pytest.raises(KeyError):
        sim.set_param("nope", 1.0)


def test_history_has_one_row_per_step_call():
    sim = make_sim(flat_scene(40))
    sim.ignite(20.0, 20.0, 3.0)
    for _ in range(7):
        sim.step(3)
    h = sim.history()
    assert set(h) == set(METRIC_KEYS)
    assert all(len(v) == 7 for v in h.values())
    assert h["t"] == sorted(h["t"])


def test_fields_uint8_and_burning_after_ignition():
    sim = make_sim(flat_scene(50))
    T, beta = sim.fields_uint8()
    assert (T == 0).all() and (beta == 255).all()
    sim.ignite(25.0, 25.0, 3.0)
    sim.step(BASE_STEPS)
    T, beta = sim.fields_uint8()
    for f in (T, beta):
        assert f.dtype == np.uint8 and f.shape == (50, 50) and f.flags.c_contiguous
    assert (T >= BURNING_T_U8).any()


def test_low_fuel_fire_dies_and_finishes():
    sim = make_sim(flat_scene(80), fuel=0.5)
    assert not sim.finished()
    sim.ignite(40.0, 40.0, 3.0)
    assert not sim.finished()
    run_until(sim, 300.0)
    assert sim.finished()
    assert sim.metrics()["burned_area"] < 200  # stayed near the ignition point


def test_full_burn_finishes_and_counts_trees():
    trees = np.array([[10.5, 10.5, 5, 1], [30.5, 30.5, 5, 1], [59.5, 0.5, 5, 1]], np.float32)
    sim = make_sim(flat_scene(60, trees))
    sim.ignite(30.0, 30.0, 3.0)
    run_until(sim, 400.0)
    assert sim.finished()
    m = sim.metrics()
    assert m["burned_area"] == pytest.approx(60 * 60)
    assert m["burned_trees"] == 3


def test_ignition_at_edge_and_accumulates():
    sim = make_sim(flat_scene(40))
    sim.ignite(0.0, 0.0, 3.0)
    sim.ignite(39.9, 39.9, 0.1)
    hot = sim.T >= sim.params["ignition_T"]
    assert hot[0, 0] and hot[-1, -1]
