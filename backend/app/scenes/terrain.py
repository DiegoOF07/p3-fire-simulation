from __future__ import annotations

import numpy as np


def grid_coords(n: int, cell_size: float) -> tuple[np.ndarray, np.ndarray]:
    # Cell-center coordinates in metres, shaped (ny, nx) for broadcasting.
    c = (np.arange(n) + 0.5) * cell_size
    return c[None, :], c[:, None]


def smooth_noise(n: int, rng: np.random.Generator, octaves: int = 4, base: int = 4) -> np.ndarray:
    # Value noise: random coarse grids, bilinearly upsampled and summed. Range ~[-1, 1].
    out = np.zeros((n, n))
    amp, total = 1.0, 0.0
    for o in range(octaves):
        k = base * 2**o + 1
        coarse = rng.uniform(-1, 1, (k, k))
        t = np.linspace(0, k - 1, n)
        i0 = np.minimum(t.astype(int), k - 2)
        f = t - i0
        rows = coarse[i0] * (1 - f)[:, None] + coarse[i0 + 1] * f[:, None]
        out += amp * (rows[:, i0] * (1 - f)[None, :] + rows[:, i0 + 1] * f[None, :])
        total += amp
        amp *= 0.5
    return out / total


def gaussian_hill(x: np.ndarray, y: np.ndarray, cx: float, cy: float, height: float, sigma: float) -> np.ndarray:
    return height * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma**2))


def valley(x: np.ndarray, y: np.ndarray, cx: float, depth: float, half_width: float, tilt: float) -> np.ndarray:
    # Valley along +y: floor at x = cx, walls rising `depth` metres; floor rises `tilt` m/m along y.
    return depth * (1 - np.exp(-(((x - cx) / half_width) ** 2))) + tilt * y
