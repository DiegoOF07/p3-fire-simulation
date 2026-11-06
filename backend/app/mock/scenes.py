from __future__ import annotations

import numpy as np

from app.contracts import PresetInfo, Scene

GRID = 200
CELL_SIZE = 1.0


def list_presets() -> list[PresetInfo]:
    return [{"id": "flat", "name": "Flat", "description": "Flat terrain with random trees"}]


def build_scene(preset: str, density: float, seed: int) -> Scene:
    if preset != "flat":
        raise KeyError(f"unknown preset {preset!r}")
    rng = np.random.default_rng(seed)
    size = GRID * CELL_SIZE
    n = int(density * GRID * GRID / 10)  # density 1 -> one tree per 10 cells
    trees = np.column_stack([
        rng.uniform(0, size, n),
        rng.uniform(0, size, n),
        rng.uniform(4, 10, n),
        rng.uniform(1, 2.5, n),
    ])
    return Scene(np.zeros((GRID, GRID)), CELL_SIZE, trees)
