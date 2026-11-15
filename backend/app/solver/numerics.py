from __future__ import annotations

import numpy as np

from app.solver.model import U_EPS, PhysicalParams

SAFETY = 0.5


def stable_dt(
    p: PhysicalParams,
    dx: float,
    beta_max: float,
    v_max_x: float = 0.0,
    v_max_y: float = 0.0,
    A_eff: float | None = None,
) -> float:
    # Explicit Euler with centered diffusion + upwind advection: dt ≤ 1 / (4κ/dx² + (|vx|+|vy|)/dx).
    # Reaction: max_T d/dT [A β e^{-B/(T-T_inf)}] sits at T - T_inf = B/2 and equals A β e^{-2} 4/B.
    A = p.A if A_eff is None else A_eff
    transport = 1.0 / (4.0 * p.kappa / (dx * dx) + (abs(v_max_x) + abs(v_max_y)) / dx)
    reaction_max = A * max(beta_max, 0.0) * np.exp(-2.0) * 4.0 / p.B
    return float(SAFETY * min(transport, 1.0 / (p.C + reaction_max + p.eps)))


class Workspace:
    """Preallocated buffers so the time loop allocates nothing."""

    def __init__(self, ny: int, nx: int) -> None:
        self.ghost = np.empty((ny + 2, nx + 2))
        self.lap = np.empty((ny, nx))
        self.rate = np.empty((ny, nx))
        self.tmp = np.empty((ny, nx))
        self.adv = np.empty((ny, nx))
        self.diff = np.empty((ny, nx))
        self.vel = np.empty((ny, nx))
        self.vx = np.empty((ny, nx))
        self.vy = np.empty((ny, nx))


def laplacian_neumann(T: np.ndarray, dx: float, ws: Workspace) -> np.ndarray:
    g = ws.ghost
    g[1:-1, 1:-1] = T
    g[0, 1:-1] = T[0]
    g[-1, 1:-1] = T[-1]
    g[1:-1, 0] = T[:, 0]
    g[1:-1, -1] = T[:, -1]
    lap = ws.lap
    np.add(g[:-2, 1:-1], g[2:, 1:-1], out=lap)
    lap += g[1:-1, :-2]
    lap += g[1:-1, 2:]
    lap -= 4.0 * T
    lap *= 1.0 / (dx * dx)
    return lap


def _upwind_axis(
    T: np.ndarray, back: np.ndarray, fwd: np.ndarray, v: float | np.ndarray,
    dx: float, ws: Workspace, out: np.ndarray,
) -> None:
    # out += max(v,0)·(T - back)/dx + min(v,0)·(fwd - T)/dx
    if not isinstance(v, np.ndarray):
        if v > 0:
            np.subtract(T, back, out=ws.diff)
        elif v < 0:
            np.subtract(fwd, T, out=ws.diff)
        else:
            return
        ws.diff *= v / dx
        out += ws.diff
        return
    inv_dx = 1.0 / dx
    np.maximum(v, 0.0, out=ws.vel)
    np.subtract(T, back, out=ws.diff)
    ws.diff *= ws.vel
    ws.diff *= inv_dx
    out += ws.diff
    np.minimum(v, 0.0, out=ws.vel)
    np.subtract(fwd, T, out=ws.diff)
    ws.diff *= ws.vel
    ws.diff *= inv_dx
    out += ws.diff


def advection_upwind(
    T: np.ndarray, vx: float | np.ndarray, vy: float | np.ndarray, dx: float, ws: Workspace
) -> np.ndarray:
    # v·∇T with first-order upwind; reuses the ghost cells filled by laplacian_neumann.
    g = ws.ghost
    adv = ws.adv
    adv.fill(0.0)
    _upwind_axis(T, g[1:-1, :-2], g[1:-1, 2:], vx, dx, ws, adv)
    _upwind_axis(T, g[:-2, 1:-1], g[2:, 1:-1], vy, dx, ws, adv)
    return adv


def reaction_rate(T: np.ndarray, p: PhysicalParams, ws: Workspace) -> np.ndarray:
    # exp(-B / (T - T_inf)); clamping the excess at U_EPS·T_inf underflows to exactly 0.
    r = ws.rate
    np.subtract(T, p.T_inf, out=r)
    np.maximum(r, U_EPS * p.T_inf, out=r)
    np.divide(-p.B, r, out=r)
    np.exp(r, out=r)
    return r
