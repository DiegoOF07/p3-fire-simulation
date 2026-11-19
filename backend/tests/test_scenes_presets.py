import numpy as np
import pytest

from app.scenes import build_scene, list_presets
from app.scenes.presets import RIVER_WIDTH, SIZE, _river_center
from app.solver.fuel import tree_coverage

MAIN = ["flat", "hill", "valley", "river_slope", "firebreak"]


def slope(scene):
    gy, gx = np.gradient(scene.heightmap.astype(float), scene.cell_size)
    return np.hypot(gx, gy)


def test_main_presets_listed():
    ids = [p["id"] for p in list_presets()]
    assert ids[:5] == MAIN
    assert all(set(p) == {"id", "name", "description"} for p in list_presets())


@pytest.mark.parametrize("preset", MAIN)
def test_deterministic_and_valid(preset):
    a, b = build_scene(preset, 1.0, 3), build_scene(preset, 1.0, 3)
    np.testing.assert_array_equal(a.heightmap, b.heightmap)
    np.testing.assert_array_equal(a.trees, b.trees)
    assert a.heightmap.shape == (200, 200) and a.heightmap.dtype == np.float32
    assert len(build_scene(preset, 0.0, 3).trees) == 0
    assert (a.trees[:, 3] > 0).all() and (a.trees[:, 2] > 0).all()


def test_terrain_independent_of_density():
    np.testing.assert_array_equal(build_scene("hill", 0.3, 1).heightmap, build_scene("hill", 1.5, 1).heightmap)


def test_negative_density_rejected():
    with pytest.raises(ValueError):
        build_scene("flat", -1, 0)


def test_density_one_crown_coverage():
    cov = tree_coverage(build_scene("flat", 1.0, 0)).mean()
    assert 0.55 < cov < 0.8


def test_flat_is_flat():
    assert (build_scene("flat", 1, 0).heightmap == 0).all()


def test_hill_slopes_in_range():
    s = slope(build_scene("hill", 1, 0))
    assert 0.4 < s.max() < 0.7


def test_valley_floor_lower_than_walls():
    h = build_scene("valley", 1, 0).heightmap
    assert h[:, 100].mean() + 20 < h[:, [0, -1]].mean()


@pytest.mark.parametrize("width", [2, 8, 32])
def test_firebreak_strip_has_no_crowns(width):
    scene = build_scene(f"firebreak_{width}", 1.5, 0)
    x, r = scene.trees[:, 0], scene.trees[:, 3]
    assert (np.abs(x - SIZE / 2) - r >= width / 2 - 1e-4).all()


def test_river_has_no_crowns():
    scene = build_scene("river_slope", 1.5, 0)
    rng = np.random.default_rng([0, 0])
    phase = rng.uniform(0, 2 * np.pi)
    x, y, r = scene.trees[:, 0], scene.trees[:, 1], scene.trees[:, 3]
    assert (np.abs(y - _river_center(x, phase)) - r >= RIVER_WIDTH / 2 - 1e-4).all()
    assert len(scene.trees) > 1000
