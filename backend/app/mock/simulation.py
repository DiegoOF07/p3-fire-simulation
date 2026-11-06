from __future__ import annotations

import numpy as np

from app.contracts import (
    METRIC_KEYS,
    Metrics,
    ParamSpec,
    Scene,
    T_U8_MIN,
    quantize_beta,
    quantize_T,
)

DT = 0.5  # s per step
T_AMBIENT = T_U8_MIN
T_PEAK = 1200.0


def param_specs() -> list[ParamSpec]:
    return [
        {"name": "spread_speed", "label": "Spread speed", "min": 0.1, "max": 5.0,
         "default": 1.0, "step": 0.1, "unit": "m/s", "live": True},
        {"name": "burn_time", "label": "Burn time", "min": 5.0, "max": 120.0,
         "default": 30.0, "step": 1.0, "unit": "s", "live": True},
    ]


class MockSimulation:
    """Heat circles growing at constant speed; each cell burns and cools by its age since arrival."""

    def __init__(self, scene: Scene, params: dict[str, float]) -> None:
        self.scene = scene
        self.params = {s["name"]: s["default"] for s in param_specs()} | params
        cs = scene.cell_size
        ys, xs = np.mgrid[0:scene.ny, 0:scene.nx]
        self._cx = (xs + 0.5) * cs
        self._cy = (ys + 0.5) * cs
        self._arrival = np.full((scene.ny, scene.nx), np.inf)
        self._fronts: list[tuple[np.ndarray, float]] = []  # (distance grid, radius)
        self._tree_cells = self._cells_of(scene.trees[:, 0], scene.trees[:, 1])
        self.t = 0.0
        self._history: dict[str, list[float]] = {k: [] for k in METRIC_KEYS}

    def _cells_of(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        s = self.scene
        rows = np.clip((y // s.cell_size).astype(int), 0, s.ny - 1)
        cols = np.clip((x // s.cell_size).astype(int), 0, s.nx - 1)
        return rows, cols

    def ignite(self, x: float, y: float, radius: float) -> None:
        dist = np.hypot(self._cx - x, self._cy - y)
        self._fronts.append((dist, max(radius, self.scene.cell_size)))
        self._mark_arrivals()

    def _mark_arrivals(self) -> None:
        for dist, r in self._fronts:
            reached = (dist <= r) & np.isinf(self._arrival)
            self._arrival[reached] = self.t

    def step(self, n_steps: int) -> None:
        speed = self.params["spread_speed"]
        for _ in range(n_steps):
            self.t += DT
            self._fronts = [(d, r + speed * DT) for d, r in self._fronts]
            self._mark_arrivals()
        m = self.metrics()
        for k in METRIC_KEYS:
            self._history[k].append(float(m[k]))

    def set_param(self, name: str, value: float) -> None:
        if name not in self.params:
            raise KeyError(f"unknown param {name!r}")
        self.params[name] = float(value)

    def _age(self) -> np.ndarray:
        return self.t - self._arrival  # -inf where not reached

    def _fields(self) -> tuple[np.ndarray, np.ndarray]:
        tau = self.params["burn_time"] / 3
        age = np.maximum(self._age(), 0.0)
        reached = np.isfinite(self._arrival)
        decay = np.where(reached, np.exp(-age / tau), 0.0)
        T = T_AMBIENT + (T_PEAK - T_AMBIENT) * decay
        beta = np.where(reached, decay, 1.0)
        return T, beta

    def fields_uint8(self) -> tuple[np.ndarray, np.ndarray]:
        T, beta = self._fields()
        return quantize_T(T), quantize_beta(beta)

    def _burning(self) -> np.ndarray:
        age = self._age()
        return (age >= 0) & (age < self.params["burn_time"])

    def metrics(self) -> Metrics:
        reached = np.isfinite(self._arrival)
        T, _ = self._fields()
        rows, cols = self._tree_cells
        any_burning = bool(self._burning().any())
        return {
            "t": self.t,
            "burned_area": float(reached.sum()) * self.scene.cell_size ** 2,
            "burned_trees": int(reached[rows, cols].sum()),
            "front_speed": self.params["spread_speed"] if any_burning else 0.0,
            "T_max": float(T.max()),
        }

    def history(self) -> dict[str, list[float]]:
        return {k: list(v) for k, v in self._history.items()}

    def finished(self) -> bool:
        return bool(np.isfinite(self._arrival).all()) and not self._burning().any()
