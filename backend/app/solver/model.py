from __future__ import annotations

from dataclasses import asdict, dataclass, replace

import numpy as np

# Reaction uses the shifted Arrhenius law exp(-B / (T - T_inf)), zero at or below ambient,
# so unburnt fuel never smoulders (see docs/modelo.md).


@dataclass(frozen=True)
class PhysicalParams:
    kappa: float = 0.5  # m²/s, effective diffusivity (conduction + radiation)
    A: float = 1500.0  # K/s, heating per unit fuel
    B: float = 690.0  # K, activation temperature
    C: float = 0.1  # 1/s, cooling to ambient
    eps: float = 0.8  # 1/s, fuel consumption rate
    T_inf: float = 300.0  # K, ambient temperature

    def with_(self, **changes: float) -> PhysicalParams:
        return replace(self, **changes)


# (min, max) in physical units; defaults sit inside every range.
PARAM_RANGES: dict[str, tuple[float, float]] = {
    "kappa": (0.1, 2.0),
    "A": (500.0, 3000.0),
    "B": (300.0, 1200.0),
    "C": (0.02, 0.5),
    "eps": (0.2, 3.0),
    "T_inf": (270.0, 320.0),
}


@dataclass(frozen=True)
class Dimensionless:
    a: float  # A / (C T_inf)
    b: float  # B / T_inf
    e: float  # eps / C


def to_dimensionless(p: PhysicalParams) -> Dimensionless:
    return Dimensionless(a=p.A / (p.C * p.T_inf), b=p.B / p.T_inf, e=p.eps / p.C)


def from_dimensionless(
    d: Dimensionless, kappa: float, C: float, T_inf: float
) -> PhysicalParams:
    return PhysicalParams(
        kappa=kappa, A=d.a * C * T_inf, B=d.b * T_inf, C=C, eps=d.e * C, T_inf=T_inf
    )


def length_scale(p: PhysicalParams) -> float:
    return float(np.sqrt(p.kappa / p.C))


def time_scale(p: PhysicalParams) -> float:
    return 1.0 / p.C


def speed_scale(p: PhysicalParams) -> float:
    return float(np.sqrt(p.kappa * p.C))


def T_to_u(T, p: PhysicalParams):
    return (np.asarray(T, dtype=float) - p.T_inf) / p.T_inf


def u_to_T(u, p: PhysicalParams):
    return p.T_inf * (1.0 + np.asarray(u, dtype=float))


# Below this excess temperature exp(-b/u) underflows to 0 anyway.
U_EPS = 1e-6


def reaction_rate_u(u, b: float):
    u = np.asarray(u, dtype=float)
    out = np.zeros_like(u)
    hot = u > U_EPS
    out[hot] = np.exp(-b / u[hot])
    return out


def reaction_rate(T, p: PhysicalParams):
    return reaction_rate_u(T_to_u(T, p), p.B / p.T_inf)


def cell_rhs(T, beta, p: PhysicalParams):
    r = reaction_rate(T, p)
    dT = p.A * beta * r - p.C * (np.asarray(T, dtype=float) - p.T_inf)
    dbeta = -p.eps * beta * r
    return dT, dbeta


def cell_rhs_u(u, beta, d: Dimensionless):
    r = reaction_rate_u(u, d.b)
    return d.a * beta * r - u, -d.e * beta * r


def frozen_fuel_f(u, a: float, b: float, beta: float):
    return a * beta * reaction_rate_u(u, b) - np.asarray(u, dtype=float)


def frozen_fuel_df(u, a: float, b: float, beta: float):
    u = np.asarray(u, dtype=float)
    r = reaction_rate_u(u, b)
    safe = np.where(u > U_EPS, u, 1.0)
    return np.where(u > U_EPS, a * beta * r * b / safe**2, 0.0) - 1.0


def _bisect(f, lo: float, hi: float, tol: float = 1e-12) -> float:
    # Kept dependency-free so the runtime solver does not need scipy.
    f_lo = f(lo)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        f_mid = f(mid)
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
        if hi - lo < tol * max(1.0, abs(mid)):
            break
    return 0.5 * (lo + hi)


@dataclass(frozen=True)
class Equilibrium:
    u: float
    stable: bool


def frozen_fuel_equilibria(a: float, b: float, beta: float) -> list[Equilibrium]:
    # u = 0 is always a root; the others solve u = a β exp(-b/u), so u < a β.
    roots = [0.0]
    u_max = a * beta
    if u_max > 0:
        grid = np.geomspace(1e-6, u_max * (1 + 1e-9), 20000)
        f = frozen_fuel_f(grid, a, b, beta)
        for i in np.nonzero(np.sign(f[:-1]) * np.sign(f[1:]) < 0)[0]:
            roots.append(float(_bisect(lambda x: float(frozen_fuel_f(x, a, b, beta)), grid[i], grid[i + 1])))
    return [Equilibrium(r, bool(frozen_fuel_df(r, a, b, beta) < 0)) for r in roots]


def ignition_threshold(a: float, b: float, beta: float = 1.0) -> float | None:
    # Middle (unstable) equilibrium: the minimum excess temperature that ignites.
    unstable = [eq.u for eq in frozen_fuel_equilibria(a, b, beta) if not eq.stable]
    return unstable[0] if unstable else None


def critical_fuel(a: float, b: float) -> float:
    # Saddle-node: u = aβ e^{-b/u} and 1 = aβ e^{-b/u} b/u² meet at u = b, so β* = e b / a.
    return float(np.e * b / a)


def as_dict(p: PhysicalParams) -> dict[str, float]:
    return asdict(p)
