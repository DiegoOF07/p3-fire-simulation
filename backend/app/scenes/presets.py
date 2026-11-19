from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

import numpy as np

from app.contracts import PresetInfo, Scene
from app.scenes.terrain import gaussian_hill, grid_coords, smooth_noise, valley
from app.scenes.trees import ClearanceFn, place_trees

GRID = 200
CELL_SIZE = 1.0
SIZE = GRID * CELL_SIZE

FIREBREAK_WIDTH = 8.0
FIREBREAK_VARIANTS = (2, 4, 6, 8, 12, 16, 24, 32)  # m, for the critical-width experiment
RIVER_WIDTH = 6.0
SLOPE = 0.25  # river_slope: 25 % grade rising along +y

Builder = Callable[[np.random.Generator, float], tuple[np.ndarray, ClearanceFn | None]]


@dataclass(frozen=True)
class Preset:
    info: PresetInfo
    build: Builder


def _flat(rng, density):
    return np.zeros((GRID, GRID)), None


def _hill(rng, density):
    x, y = grid_coords(GRID, CELL_SIZE)
    # Peak 30 m, sigma 35 m: steepest flank ~52 %, gentle near the top and the base.
    h = gaussian_hill(x, y, SIZE / 2, SIZE / 2, 30.0, 35.0) + 0.8 * smooth_noise(GRID, rng)
    return h - h.min(), None


def _valley(rng, density):
    x, y = grid_coords(GRID, CELL_SIZE)
    h = valley(x, y, SIZE / 2, depth=30.0, half_width=45.0, tilt=0.08) + 0.8 * smooth_noise(GRID, rng)
    return h - h.min(), None


def _river_center(x: np.ndarray, phase: float) -> np.ndarray:
    return SIZE / 2 + 12.0 * np.sin(2 * np.pi * x / 120.0 + phase)


def _river_slope(rng, density):
    x, y = grid_coords(GRID, CELL_SIZE)
    phase = rng.uniform(0, 2 * np.pi)
    dist = np.abs(y - _river_center(x, phase))
    # Shallow channel carved into the slope.
    channel = 1.2 * np.clip(1 - dist / (RIVER_WIDTH / 2 + 2), 0, 1)
    h = SLOPE * y - channel + 0.4 * smooth_noise(GRID, rng)

    def clearance(px, py):
        return np.abs(py - _river_center(px, phase)) - RIVER_WIDTH / 2

    return h - h.min(), clearance


def _firebreak(width: float) -> Builder:
    def build(rng, density):
        def clearance(px, py):
            return np.abs(px - SIZE / 2) - width / 2

        return np.zeros((GRID, GRID)), clearance

    return build


PRESETS: dict[str, Preset] = {
    p.info["id"]: p
    for p in [
        Preset({"id": "flat", "name": "Plano",
                "description": "Terreno plano con árboles al azar. Validación, densidad, humedad y viento."}, _flat),
        Preset({"id": "hill", "name": "Colina",
                "description": "Colina aislada de 30 m (pendientes de 10–50 %) cubierta de bosque."}, _hill),
        Preset({"id": "valley", "name": "Valle",
                "description": "Valle a lo largo de +y con laderas de 30 m; el fondo sube suavemente."}, _valley),
        Preset({"id": "river_slope", "name": "Ladera con río",
                "description": f"Ladera de {SLOPE:.0%} cruzada por un río de {RIVER_WIDTH:g} m sin árboles."},
               _river_slope),
        Preset({"id": "firebreak", "name": "Cortafuegos",
                "description": f"Bosque plano con una franja sin árboles de {FIREBREAK_WIDTH:g} m en x = 100 m."},
               _firebreak(FIREBREAK_WIDTH)),
    ]
}
for _w in FIREBREAK_VARIANTS:
    PRESETS[f"firebreak_{_w}"] = Preset(
        {"id": f"firebreak_{_w}", "name": f"Cortafuegos {_w} m",
         "description": f"Variante de cortafuegos con franja de {_w} m (experimentos)."},
        _firebreak(float(_w)),
    )

VARIANT_ID = re.compile(r"_\d+$")


def list_presets() -> list[PresetInfo]:
    return [dict(p.info) for p in PRESETS.values()]  # type: ignore[misc]


def build_scene(preset: str, density: float, seed: int) -> Scene:
    if preset not in PRESETS:
        raise KeyError(f"unknown preset {preset!r}")
    if density < 0:
        raise ValueError("density must be >= 0")
    # Separate streams so terrain does not change with density.
    terrain_rng, tree_rng = (np.random.default_rng([seed, k]) for k in (0, 1))
    heightmap, clearance = PRESETS[preset].build(terrain_rng, density)
    heightmap = heightmap.astype(np.float32)
    trees = place_trees(tree_rng, SIZE, SIZE, density, clearance, heightmap, CELL_SIZE)
    return Scene(heightmap, CELL_SIZE, trees)
