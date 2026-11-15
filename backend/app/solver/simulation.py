from __future__ import annotations

import numpy as np

from app.contracts import (
    BURNING_T_U8,
    METRIC_KEYS,
    T_U8_MAX,
    T_U8_MIN,
    Metrics,
    Scene,
    quantize_beta,
    quantize_T,
)
from app.solver.fuel import initial_fuel, moisture_damping
from app.solver.model import ignition_threshold, to_dimensionless, u_to_T
from app.solver.numerics import (
    Workspace,
    advection_upwind,
    laplacian_neumann,
    reaction_rate,
    stable_dt,
)
from app.solver.params import param_specs, to_physical
from app.solver.wind import max_wind_speed, slope_velocity, wind_vector

T_BURNING = T_U8_MIN + BURNING_T_U8 / 255 * (T_U8_MAX - T_U8_MIN)  # "burning" on screen
BURNT_FRACTION = 0.5  # a cell counts as burned once half its fuel is gone


class FireSimulation:
    """Reaction-diffusion-advection fire model on the scene grid, explicit finite differences.

    front_speed is the growth rate of the equivalent radius √(area/π): exact for a circle,
    the mean spread rate (not the head speed) when wind or slope stretch the fire.
    """

    def __init__(self, scene: Scene, params: dict[str, float]) -> None:
        self.scene = scene
        self.params = {s["name"]: float(s["default"]) for s in param_specs()} | {
            k: float(v) for k, v in params.items()
        }
        self.p = to_physical(self.params)
        ny, nx = scene.ny, scene.nx
        cs = scene.cell_size
        self.T = np.full((ny, nx), self.p.T_inf)
        self.beta0 = initial_fuel(scene, self.params["ground_fuel"], self.params["tree_fuel"])
        self.beta = self.beta0.copy()
        self._grad_h = slope_velocity(scene.heightmap, cs, 1.0)  # ∇h, scaled by slope_factor
        self._has_slope = bool(np.any(self._grad_h[0]) or np.any(self._grad_h[1]))
        self._ws = Workspace(ny, nx)
        self._cx = (np.arange(nx) + 0.5) * cs
        self._cy = (np.arange(ny) + 0.5) * cs
        rows = np.clip((scene.trees[:, 1] // cs).astype(int), 0, ny - 1)
        cols = np.clip((scene.trees[:, 0] // cs).astype(int), 0, nx - 1)
        self._tree_cells = (rows, cols)
        self.t = 0.0
        self.ignited = False
        self._prev_radius: tuple[float, float] | None = None  # (t, equivalent radius)
        self._front_speed = 0.0
        self._history: dict[str, list[float]] = {k: [] for k in METRIC_KEYS}
        self._refresh_derived()

    def _refresh_derived(self) -> None:
        self.A_eff = self.p.A * moisture_damping(self.params["moisture"])
        gamma = self.params["slope_factor"]
        self._slope_vx = gamma * self._grad_h[0]
        self._slope_vy = gamma * self._grad_h[1]
        wind_max = max_wind_speed(self.params)
        beta_max = float(self.beta0.max(initial=0.0))
        self.dt = stable_dt(
            self.p, self.scene.cell_size, beta_max,
            wind_max + float(np.abs(self._slope_vx).max(initial=0.0)),
            wind_max + float(np.abs(self._slope_vy).max(initial=0.0)),
            self.A_eff,
        )
        d = to_dimensionless(self.p.with_(A=self.A_eff))
        u_ig = ignition_threshold(d.a, d.b, beta_max) if beta_max > 0 and self.A_eff > 0 else None
        T_ig = float(u_to_T(u_ig, self.p)) if u_ig is not None else T_BURNING
        # Below this nothing can reignite, so the fire is over.
        self._T_quiet = self.p.T_inf + 0.5 * (min(T_ig, T_BURNING) - self.p.T_inf)

    def ignite(self, x: float, y: float, radius: float) -> None:
        r = max(radius, self.scene.cell_size)
        dy2 = (self._cy - y)[:, None] ** 2
        dx2 = (self._cx - x)[None, :] ** 2
        disk = dx2 + dy2 <= r * r
        if not disk.any():
            row = int(np.clip(y // self.scene.cell_size, 0, self.scene.ny - 1))
            col = int(np.clip(x // self.scene.cell_size, 0, self.scene.nx - 1))
            disk[row, col] = True
        np.maximum(self.T, np.where(disk, self.params["ignition_T"], self.p.T_inf), out=self.T)
        self.ignited = True

    def step(self, n_steps: int) -> None:
        p, dt, ws, A = self.p, self.dt, self._ws, self.A_eff
        T, beta = self.T, self.beta
        dx = self.scene.cell_size
        for _ in range(n_steps):
            lap = laplacian_neumann(T, dx, ws)
            wx, wy = wind_vector(self.params, self.t)
            vx: float | np.ndarray = wx
            vy: float | np.ndarray = wy
            if self._has_slope:
                vx = np.add(self._slope_vx, wx, out=ws.vx)
                vy = np.add(self._slope_vy, wy, out=ws.vy)
            moving = self._has_slope or wx != 0.0 or wy != 0.0
            r = reaction_rate(T, p, ws)
            r *= beta  # β·r, used by both equations
            tmp = ws.tmp
            np.subtract(T, p.T_inf, out=tmp)
            tmp *= -p.C
            tmp += p.kappa * lap
            tmp += A * r
            if moving:
                tmp -= advection_upwind(T, vx, vy, dx, ws)
            tmp *= dt
            T += tmp
            r *= dt * p.eps
            beta -= r
            np.maximum(beta, 0.0, out=beta)
            self.t += dt
        if not np.isfinite(T).all():
            raise FloatingPointError("NaN in T")
        self._update_front_speed()
        m = self.metrics()
        for k in METRIC_KEYS:
            self._history[k].append(float(m[k]))

    def _burned(self) -> np.ndarray:
        return (self.beta0 > 0) & (self.beta <= (1.0 - BURNT_FRACTION) * self.beta0)

    def _update_front_speed(self) -> None:
        area = float(self._burned().sum()) * self.scene.cell_size**2
        radius = float(np.sqrt(area / np.pi))
        burning = bool((self.T >= T_BURNING).any())
        if self._prev_radius is not None and burning and self.t > self._prev_radius[0]:
            t0, r0 = self._prev_radius
            self._front_speed = max(0.0, (radius - r0) / (self.t - t0))
        else:
            self._front_speed = 0.0
        self._prev_radius = (self.t, radius)

    def set_param(self, name: str, value: float) -> None:
        if name not in self.params:
            raise KeyError(f"unknown param {name!r}")
        self.params[name] = float(value)
        self.p = to_physical(self.params)
        self._refresh_derived()

    def fields_uint8(self) -> tuple[np.ndarray, np.ndarray]:
        return quantize_T(self.T), quantize_beta(self.beta)

    def metrics(self) -> Metrics:
        burned = self._burned()
        rows, cols = self._tree_cells
        return {
            "t": float(self.t),
            "burned_area": float(burned.sum()) * self.scene.cell_size**2,
            "burned_trees": int(burned[rows, cols].sum()),
            "front_speed": float(self._front_speed),
            "T_max": float(self.T.max()),
        }

    def history(self) -> dict[str, list[float]]:
        return {k: list(v) for k, v in self._history.items()}

    def finished(self) -> bool:
        return self.ignited and float(self.T.max()) < self._T_quiet
