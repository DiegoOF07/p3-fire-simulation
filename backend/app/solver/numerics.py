from __future__ import annotations

import numpy as np

from app.solver.model import U_EPS, PhysicalParams

SAFETY = 0.5


def stable_dt(p: PhysicalParams, dx: float, beta_max: float) -> float:
    # Explicit Euler limits: 2D diffusion dx²/(4κ); stiffest reaction rate.
    # max_T d/dT [A β e^{-B/(T-T_inf)}] sits at T - T_inf = B/2 and equals A β e^{-2} 4/B.
    reaction_max = p.A * max(beta_max, 0.0) * np.exp(-2.0) * 4.0 / p.B
    return float(SAFETY * min(dx * dx / (4.0 * p.kappa), 1.0 / (p.C + reaction_max + p.eps)))


class Workspace:
    """Preallocated buffers so the time loop allocates nothing."""

    def __init__(self, ny: int, nx: int) -> None:
        self.ghost = np.empty((ny + 2, nx + 2))
        self.lap = np.empty((ny, nx))
        self.rate = np.empty((ny, nx))
        self.tmp = np.empty((ny, nx))


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


def reaction_rate(T: np.ndarray, p: PhysicalParams, ws: Workspace) -> np.ndarray:
    # exp(-B / (T - T_inf)); clamping the excess at U_EPS·T_inf underflows to exactly 0.
    r = ws.rate
    np.subtract(T, p.T_inf, out=r)
    np.maximum(r, U_EPS * p.T_inf, out=r)
    np.divide(-p.B, r, out=r)
    np.exp(r, out=r)
    return r
