import numpy as np
import pytest

from app.solver.model import (
    PARAM_RANGES,
    PhysicalParams,
    cell_rhs,
    critical_fuel,
    frozen_fuel_equilibria,
    from_dimensionless,
    ignition_threshold,
    reaction_rate,
    to_dimensionless,
    u_to_T,
)


def test_defaults_inside_ranges():
    p = PhysicalParams()
    for name, (lo, hi) in PARAM_RANGES.items():
        assert lo <= getattr(p, name) <= hi, name


def test_dimensionless_roundtrip():
    p = PhysicalParams(kappa=0.8, A=1200.0, B=600.0, C=0.2, eps=1.1, T_inf=290.0)
    back = from_dimensionless(to_dimensionless(p), p.kappa, p.C, p.T_inf)
    for name, value in vars(p).items():
        assert getattr(back, name) == pytest.approx(value)


def test_no_reaction_at_or_below_ambient():
    p = PhysicalParams()
    T = np.array([0.0, 250.0, p.T_inf, p.T_inf + 1e-9])
    assert np.all(np.isfinite(reaction_rate(T, p)))
    assert np.all(reaction_rate(T, p) == 0.0)
    dT, dbeta = cell_rhs(np.full(3, p.T_inf), np.ones(3), p)
    assert np.all(dT == 0.0) and np.all(dbeta == 0.0)


def test_defaults_have_three_equilibria_with_unstable_middle():
    d = to_dimensionless(PhysicalParams())
    eqs = frozen_fuel_equilibria(d.a, d.b, 1.0)
    assert [e.stable for e in eqs] == [True, False, True]
    u_ign = ignition_threshold(d.a, d.b)
    assert u_ign == pytest.approx(eqs[1].u)
    # Ignition sits between ambient and the on-screen "burning" threshold (~770 K).
    assert 300.0 < u_to_T(u_ign, PhysicalParams()) < 770.0


def test_below_critical_fuel_only_ambient_remains():
    d = to_dimensionless(PhysicalParams())
    beta_c = critical_fuel(d.a, d.b)
    assert len(frozen_fuel_equilibria(d.a, d.b, 0.95 * beta_c)) == 1
    assert len(frozen_fuel_equilibria(d.a, d.b, 1.05 * beta_c)) == 3
