import numpy as np
import pytest

from app.contracts import Scene, default_params
from app.solver import create_simulation, param_specs
from app.solver.fuel import (
    MOISTURE_EXTINCTION,
    MOISTURE_REFERENCE,
    initial_fuel,
    moisture_damping,
    rothermel_eta,
)
from app.solver.wind import WIND_COUPLING, wind_vector


def flat(n: int = 120, trees: np.ndarray | None = None) -> Scene:
    return Scene(np.zeros((n, n)), 1.0, np.zeros((0, 4)) if trees is None else trees)


def make_sim(scene: Scene, **overrides: float):
    params = default_params(param_specs()) | {"ground_fuel": 1.0} | overrides
    return create_simulation(scene, params)


def run_until(sim, t_end: float, chunk: int = 20) -> None:
    while sim.t < t_end and not sim.finished():
        sim.step(chunk)


def reach(sim, c: float) -> dict[str, float]:
    rows, cols = np.nonzero(sim._burned())
    x, y = cols + 0.5, rows + 0.5
    return {"+x": x.max() - c, "-x": c - x.min(), "+y": y.max() - c, "-y": c - y.min()}


def burn_from_center(scene: Scene, t_end: float = 50.0, **overrides: float):
    sim = make_sim(scene, **overrides)
    c = scene.width / 2
    sim.ignite(c, c, 3.0)
    run_until(sim, t_end)
    return sim, reach(sim, c)


def test_negligible_wind_ignores_speed():
    calm, _ = burn_from_center(flat())
    windy_off, _ = burn_from_center(flat(), wind_mode=0, wind_speed=15.0)
    np.testing.assert_array_equal(calm.T, windy_off.T)


@pytest.mark.parametrize("direction, ahead, behind", [(0.0, "+x", "-x"), (90.0, "+y", "-y")])
def test_constant_wind_pushes_fire_downwind(direction, ahead, behind):
    _, r = burn_from_center(flat(), wind_mode=1, wind_speed=5.0, wind_dir=direction)
    assert r[ahead] > 1.3 * r[behind], r


def test_variable_wind_is_deterministic_and_changes():
    params = default_params(param_specs()) | {"wind_mode": 2.0, "wind_speed": 10.0}
    vectors = {wind_vector(params, t) for t in (0.0, 10.0, 20.0, 40.0)}
    assert len(vectors) == 4
    a, _ = burn_from_center(flat(80), 30.0, wind_mode=2, wind_speed=10.0)
    b, _ = burn_from_center(flat(80), 30.0, wind_mode=2, wind_speed=10.0)
    np.testing.assert_array_equal(a.T, b.T)


def test_variable_wind_without_gusts_equals_constant():
    params = default_params(param_specs()) | {"wind_speed": 8.0, "wind_dir": 45.0,
                                                "wind_gust": 0.0, "wind_swing": 0.0}
    const = wind_vector(params | {"wind_mode": 1.0}, 0.0)
    assert np.hypot(*const) == pytest.approx(WIND_COUPLING * 8.0)
    for t in (0.0, 13.0, 77.0):
        assert wind_vector(params | {"wind_mode": 2.0}, t) == pytest.approx(const)


def test_cfl_holds_with_max_wind_and_slope():
    n = 60
    ramp = Scene(np.tile(1.0 * np.arange(n, dtype=float), (n, 1)), 1.0, np.zeros((0, 4)))
    sim = make_sim(ramp, wind_mode=2, wind_speed=15.0, wind_gust=1.0, slope_factor=2.0)
    v_x = WIND_COUPLING * 15.0 * 2.0 + 2.0 * 1.0
    v_y = WIND_COUPLING * 15.0 * 2.0
    assert sim.dt * (v_x + v_y) <= sim.scene.cell_size
    sim.ignite(30.0, 30.0, 3.0)
    run_until(sim, 60.0)
    assert np.isfinite(sim.T).all()
    assert (sim.beta >= 0).all() and (sim.beta <= 1).all()


def test_fire_runs_faster_upslope():
    n = 120
    ramp = Scene(np.tile(0.3 * np.arange(n, dtype=float), (n, 1)), 1.0, np.zeros((0, 4)))
    _, r = burn_from_center(ramp, slope_factor=0.5)
    assert r["+x"] > 1.3 * r["-x"], r


def test_fuel_map_from_trees():
    no_trees = flat(40)
    beta0 = initial_fuel(no_trees, 0.4, 1.0)
    assert np.all(beta0 == 0.4)
    one = flat(40, np.array([[20.5, 20.5, 6.0, 3.0]], np.float32))
    beta0 = initial_fuel(one, 0.4, 1.0)
    assert beta0[20, 20] == pytest.approx(1.0)
    assert beta0[0, 0] == pytest.approx(0.4)
    assert 0.4 <= beta0.min() and beta0.max() <= 1.0


def forest_with_gap(width: float, n: int = 120) -> Scene:
    trees = [(cx, cy, 6.0, 1.5)
             for cy in np.arange(1.0, n, 2.0) for cx in np.arange(1.0, n, 2.0)
             if not 60 <= cx < 60 + width]
    return Scene(np.zeros((n, n)), 1.0, np.array(trees, np.float32))


@pytest.mark.parametrize("width, crosses", [(2.0, True), (20.0, False)])
def test_firebreak_width(width, crosses):
    scene = forest_with_gap(width)
    sim = create_simulation(scene, default_params(param_specs()))  # default ground fuel
    sim.ignite(30.0, 60.0, 3.0)
    run_until(sim, 400.0)
    far_side = sim._burned()[:, int(60 + width) + 5:]
    assert far_side.any() == crosses


def test_moisture_damping_curve():
    assert rothermel_eta(0.0) == 1.0
    assert rothermel_eta(MOISTURE_EXTINCTION) == 0.0
    assert moisture_damping(MOISTURE_REFERENCE) == pytest.approx(1.0)
    ms = np.linspace(0.0, MOISTURE_EXTINCTION, 31)
    etas = [rothermel_eta(m) for m in ms]
    assert all(a >= b for a, b in zip(etas, etas[1:]))


def test_wetter_fuel_burns_less():
    dry, _ = burn_from_center(flat(), 60.0, moisture=MOISTURE_REFERENCE)
    wet, _ = burn_from_center(flat(), 60.0, moisture=0.15)
    soaked, _ = burn_from_center(flat(), 60.0, moisture=MOISTURE_EXTINCTION)
    a_dry, a_wet = dry.metrics()["burned_area"], wet.metrics()["burned_area"]
    assert a_wet < 0.8 * a_dry
    assert soaked.metrics()["burned_area"] < 50  # only the ignition spot
