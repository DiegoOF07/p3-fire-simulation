from __future__ import annotations

from app.contracts import ParamSpec
from app.solver.fuel import MOISTURE_EXTINCTION, MOISTURE_REFERENCE
from app.solver.model import PARAM_RANGES, PhysicalParams

_DEFAULTS = PhysicalParams()


def _physical(name: str, label: str, unit: str, step: float, live: bool = True) -> ParamSpec:
    lo, hi = PARAM_RANGES[name]
    return {"name": name, "label": label, "min": lo, "max": hi,
            "default": getattr(_DEFAULTS, name), "step": step, "unit": unit, "live": live}


def _spec(name: str, label: str, lo: float, hi: float, default: float, step: float,
          unit: str = "", live: bool = True) -> ParamSpec:
    return {"name": name, "label": label, "min": lo, "max": hi, "default": default,
            "step": step, "unit": unit, "live": live}


def param_specs() -> list[ParamSpec]:
    return [
        _physical("kappa", "Heat diffusivity", "m²/s", 0.05),
        _physical("A", "Reaction heat", "K/s", 50.0),
        _physical("B", "Activation temperature", "K", 10.0),
        _physical("C", "Cooling rate", "1/s", 0.01),
        _physical("eps", "Fuel burn rate", "1/s", 0.05),
        _physical("T_inf", "Ambient temperature", "K", 1.0, live=False),
        _spec("ignition_T", "Ignition temperature", 600.0, 1500.0, 1200.0, 10.0, "K"),
        # Fuel: ground (grass) sits below the ~0.7 propagation threshold, so gaps stop the fire.
        _spec("ground_fuel", "Ground fuel", 0.0, 1.0, 0.4, 0.05, live=False),
        _spec("tree_fuel", "Tree fuel", 0.0, 1.0, 1.0, 0.05, live=False),
        _spec("moisture", "Fuel moisture", 0.0, MOISTURE_EXTINCTION, MOISTURE_REFERENCE, 0.01, live=False),
        # 0 = none, 1 = constant, 2 = variable
        _spec("wind_mode", "Wind mode (0 none, 1 constant, 2 variable)", 0.0, 2.0, 0.0, 1.0),
        _spec("wind_speed", "Wind speed", 0.0, 15.0, 5.0, 0.5, "m/s"),
        _spec("wind_dir", "Wind direction (to)", 0.0, 360.0, 0.0, 5.0, "°"),
        _spec("wind_gust", "Gust amplitude", 0.0, 1.0, 0.5, 0.05),
        _spec("wind_period", "Gust period", 10.0, 300.0, 60.0, 5.0, "s"),
        _spec("wind_swing", "Direction swing", 0.0, 90.0, 30.0, 5.0, "°"),
        _spec("slope_factor", "Slope effect", 0.0, 2.0, 0.5, 0.05, "m/s"),
    ]


def to_physical(params: dict[str, float]) -> PhysicalParams:
    return PhysicalParams(**{k: float(params[k]) for k in PARAM_RANGES})
