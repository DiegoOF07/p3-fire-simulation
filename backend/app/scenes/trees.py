from __future__ import annotations

from typing import Callable

import numpy as np

# density = 1 -> one tree per 10 m² (same as the mock): crowns cover ~64 % of the ground.
AREA_PER_TREE = 10.0
RADIUS_RANGE = (1.0, 2.5)
HEIGHT_RANGE = (4.0, 10.0)

# Distance (m) from a point to the nearest no-tree zone; crowns must not reach it.
ClearanceFn = Callable[[np.ndarray, np.ndarray], np.ndarray]


def place_trees(
    rng: np.random.Generator,
    width: float,
    depth: float,
    density: float,
    clearance: ClearanceFn | None = None,
    heightmap: np.ndarray | None = None,
    cell_size: float = 1.0,
) -> np.ndarray:
    # Uniform random placement; candidates whose crown would touch a clearing are dropped,
    # so the local density outside clearings matches `density`.
    n = int(round(density * width * depth / AREA_PER_TREE))
    if n <= 0:
        return np.zeros((0, 4), np.float32)
    x = rng.uniform(0, width, n)
    y = rng.uniform(0, depth, n)
    r = rng.uniform(*RADIUS_RANGE, n)
    h = rng.uniform(*HEIGHT_RANGE, n)
    keep = np.ones(n, bool)
    if clearance is not None:
        keep = clearance(x, y) > r
    trees = np.column_stack([x, y, h, r])[keep]
    if heightmap is not None and len(trees):
        # Slightly shorter trees high up, purely cosmetic.
        ny, nx = heightmap.shape
        col = np.minimum((trees[:, 0] // cell_size).astype(int), nx - 1)
        row = np.minimum((trees[:, 1] // cell_size).astype(int), ny - 1)
        z = heightmap[row, col]
        span = float(np.ptp(heightmap)) or 1.0
        trees[:, 2] *= 1 - 0.25 * (z - heightmap.min()) / span
    return trees.astype(np.float32)
