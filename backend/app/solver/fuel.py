from __future__ import annotations

import numpy as np

from app.contracts import Scene

MOISTURE_EXTINCTION = 0.3  # m_x: dead-fuel moisture of extinction
MOISTURE_REFERENCE = 0.05  # A is calibrated at this (dry-season) moisture


def tree_coverage(scene: Scene) -> np.ndarray:
    # Crown footprint per cell in [0, 1], with a one-cell soft edge.
    ny, nx, cs = scene.ny, scene.nx, scene.cell_size
    cov = np.zeros((ny, nx))
    for x, y, _, r in scene.trees:
        if r <= 0:
            continue
        c0 = max(int((x - r) // cs) - 1, 0)
        c1 = min(int((x + r) // cs) + 2, nx)
        r0 = max(int((y - r) // cs) - 1, 0)
        r1 = min(int((y + r) // cs) + 2, ny)
        if c0 >= c1 or r0 >= r1:
            continue
        cx = (np.arange(c0, c1) + 0.5) * cs
        cy = (np.arange(r0, r1) + 0.5) * cs
        d = np.hypot(cx[None, :] - x, cy[:, None] - y)
        disk = np.clip((r - d) / cs + 0.5, 0.0, 1.0)
        np.maximum(cov[r0:r1, c0:c1], disk, out=cov[r0:r1, c0:c1])
    return cov


def initial_fuel(scene: Scene, ground: float, tree: float) -> np.ndarray:
    return ground + (tree - ground) * tree_coverage(scene)


def rothermel_eta(m: float, m_x: float = MOISTURE_EXTINCTION) -> float:
    # Rothermel (1972) moisture damping coefficient, 1 when dry and 0 at extinction.
    r = max(m / m_x, 0.0)
    if r >= 1.0:
        return 0.0
    eta = 1.0 - 2.59 * r + 5.11 * r**2 - 3.52 * r**3
    return float(min(max(eta, 0.0), 1.0))


def moisture_damping(m: float) -> float:
    # Heat release factor relative to the calibration moisture: 1 at MOISTURE_REFERENCE.
    return rothermel_eta(m) / rothermel_eta(MOISTURE_REFERENCE)
