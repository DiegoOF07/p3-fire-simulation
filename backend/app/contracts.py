from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, NotRequired, Protocol, TypedDict

import numpy as np

# T range mapped to 0..255; agree with P2.
T_U8_MIN = 300.0
T_U8_MAX = 1500.0

# Mirrored in frontend/src/core/protocol.ts.
BURNING_T_U8 = 100
BURNT_BETA_U8 = 25


def quantize_T(T: np.ndarray) -> np.ndarray:
    scaled = (T - T_U8_MIN) * (255.0 / (T_U8_MAX - T_U8_MIN))
    return np.clip(np.rint(scaled), 0, 255).astype(np.uint8)


def quantize_beta(beta: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(beta * 255.0), 0, 255).astype(np.uint8)


@dataclass
class Scene:
    heightmap: np.ndarray  # (ny, nx) float32, m
    cell_size: float  # m per cell
    trees: np.ndarray  # (n, 4) float32: x, y, height, radius

    def __post_init__(self) -> None:
        self.heightmap = np.ascontiguousarray(self.heightmap, dtype=np.float32)
        self.trees = np.ascontiguousarray(self.trees, dtype=np.float32).reshape(-1, 4)
        if self.heightmap.ndim != 2:
            raise ValueError(f"heightmap must be 2D, got shape {self.heightmap.shape}")
        if self.cell_size <= 0:
            raise ValueError("cell_size must be positive")

    @property
    def ny(self) -> int:
        return self.heightmap.shape[0]

    @property
    def nx(self) -> int:
        return self.heightmap.shape[1]

    @property
    def width(self) -> float:
        return self.nx * self.cell_size

    @property
    def depth(self) -> float:
        return self.ny * self.cell_size


class PresetInfo(TypedDict):
    id: str
    name: str
    description: str


# app/scenes exposes list_presets() and build_scene(preset, density, seed).
BuildScene = Callable[[str, float, int], Scene]


class ParamSpec(TypedDict):
    name: str
    min: float
    max: float
    default: float
    live: bool  # False: only before start
    label: NotRequired[str]
    step: NotRequired[float]
    unit: NotRequired[str]


def default_params(specs: list[ParamSpec]) -> dict[str, float]:
    return {s["name"]: s["default"] for s in specs}


class Metrics(TypedDict):
    t: float  # s
    burned_area: float  # m²
    burned_trees: int
    front_speed: float  # m/s
    T_max: float


METRIC_KEYS: tuple[str, ...] = tuple(Metrics.__annotations__)


class Simulation(Protocol):
    def ignite(self, x: float, y: float, radius: float) -> None: ...

    def step(self, n_steps: int) -> None: ...

    def set_param(self, name: str, value: float) -> None: ...

    def fields_uint8(self) -> tuple[np.ndarray, np.ndarray]:
        """(T, β) as contiguous (ny, nx) uint8, via quantize_T / quantize_beta."""
        ...

    def metrics(self) -> Metrics: ...

    def history(self) -> dict[str, list[float]]:
        """One list per METRIC_KEYS entry."""
        ...

    def finished(self) -> bool:
        """True once something was ignited and nothing is burning anymore."""
        ...


SimFactory = Callable[[Scene, dict[str, float]], Simulation]
