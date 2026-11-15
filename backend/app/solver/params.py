from __future__ import annotations

from app.contracts import ParamSpec
from app.solver.model import PARAM_RANGES, PhysicalParams

_DEFAULTS = PhysicalParams()

# Uniform initial fuel until the tree-based fuel map lands.
FUEL_DEFAULT = 1.0
IGNITION_T_DEFAULT = 1200.0  # K


def _physical(name: str, label: str, unit: str, step: float, live: bool = True) -> ParamSpec:
    lo, hi = PARAM_RANGES[name]
    return {"name": name, "label": label, "min": lo, "max": hi,
            "default": getattr(_DEFAULTS, name), "step": step, "unit": unit, "live": live}


def param_specs() -> list[ParamSpec]:
    return [
        _physical("kappa", "Heat diffusivity", "m²/s", 0.05),
        _physical("A", "Reaction heat", "K/s", 50.0),
        _physical("B", "Activation temperature", "K", 10.0),
        _physical("C", "Cooling rate", "1/s", 0.01),
        _physical("eps", "Fuel burn rate", "1/s", 0.05),
        _physical("T_inf", "Ambient temperature", "K", 1.0, live=False),
        {"name": "fuel", "label": "Fuel load", "min": 0.0, "max": 1.0, "default": FUEL_DEFAULT,
         "step": 0.05, "unit": "", "live": False},
        {"name": "ignition_T", "label": "Ignition temperature", "min": 600.0, "max": 1500.0,
         "default": IGNITION_T_DEFAULT, "step": 10.0, "unit": "K", "live": True},
    ]


def to_physical(params: dict[str, float]) -> PhysicalParams:
    return PhysicalParams(**{k: float(params[k]) for k in PARAM_RANGES})
