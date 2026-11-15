from __future__ import annotations

import math

import numpy as np

# Fraction of the real wind that carries heat in the model (effective advection speed).
WIND_COUPLING = 0.05

WIND_NONE, WIND_CONSTANT, WIND_VARIABLE = 0, 1, 2
# Direction swing period relative to the gust period; irrational so they never sync.
SWING_PERIOD_RATIO = 1.7


def wind_mode(params: dict[str, float]) -> int:
    return int(round(params["wind_mode"]))


def wind_vector(params: dict[str, float], t: float) -> tuple[float, float]:
    # Effective advection velocity (m/s); direction is where the wind blows to, 0° = +x, 90° = +y.
    mode = wind_mode(params)
    if mode == WIND_NONE:
        return 0.0, 0.0
    speed = params["wind_speed"]
    angle = math.radians(params["wind_dir"])
    if mode == WIND_VARIABLE:
        period = params["wind_period"]
        speed *= 1.0 + params["wind_gust"] * math.sin(2 * math.pi * t / period)
        angle += math.radians(params["wind_swing"]) * math.sin(
            2 * math.pi * t / (SWING_PERIOD_RATIO * period)
        )
    v = WIND_COUPLING * speed
    return v * math.cos(angle), v * math.sin(angle)


def max_wind_speed(params: dict[str, float]) -> float:
    mode = wind_mode(params)
    if mode == WIND_NONE:
        return 0.0
    gust = params["wind_gust"] if mode == WIND_VARIABLE else 0.0
    return WIND_COUPLING * params["wind_speed"] * (1.0 + gust)


def slope_velocity(heightmap: np.ndarray, cell_size: float, factor: float) -> tuple[np.ndarray, np.ndarray]:
    # Upslope effective wind: factor·∇h; heightmap rows are y, columns x.
    if heightmap.shape[0] < 2 or heightmap.shape[1] < 2:
        z = np.zeros(heightmap.shape)
        return z, z.copy()
    dh_dy, dh_dx = np.gradient(heightmap.astype(np.float64), cell_size)
    return factor * dh_dx, factor * dh_dy
