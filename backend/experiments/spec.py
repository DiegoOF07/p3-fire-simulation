from __future__ import annotations

import itertools
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app import providers
from app.protocol import SPEEDS

SCENE_KEYS = {"preset", "density", "seed"}
SCENE_DEFAULTS = {"density": 1.0, "seed": 0}
RUN_DEFAULTS = {"speed": 1, "max_frames": 100_000}
NAME_RE = re.compile(r"^[a-z0-9_]+$")


class SpecError(ValueError):
    pass


@dataclass(frozen=True)
class RunConfig:
    """One concrete run after expanding the sweeps."""

    index: int
    scene: dict[str, Any]
    params: dict[str, float]
    varied: dict[str, Any]  # only the swept values, e.g. {"scene.density": 0.4}


@dataclass
class Experiment:
    name: str
    question: str
    scene: dict[str, Any]
    params: dict[str, Any]
    ignite: list[tuple[float, float]]
    max_time: float
    speed: int
    max_frames: int
    source: str = ""
    runs: list[RunConfig] = field(default_factory=list)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def _check_keys(section: str, data: dict, allowed: set[str]) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise SpecError(f"[{section}] unknown keys: {', '.join(sorted(unknown))}")


def _expand(scene: dict[str, Any], params: dict[str, Any]) -> list[RunConfig]:
    axes = [(f"scene.{k}", _as_list(v)) for k, v in scene.items()]
    axes += [(f"params.{k}", _as_list(v)) for k, v in params.items()]
    swept = {key for key, values in axes if len(values) > 1}
    runs = []
    for i, combo in enumerate(itertools.product(*(values for _, values in axes))):
        chosen = dict(zip((key for key, _ in axes), combo))
        runs.append(RunConfig(
            index=i,
            scene={k.removeprefix("scene."): v for k, v in chosen.items() if k.startswith("scene.")},
            params={k.removeprefix("params."): float(v) for k, v in chosen.items() if k.startswith("params.")},
            varied={k: v for k, v in chosen.items() if k in swept},
        ))
    return runs


def parse(text: str, source: str = "") -> Experiment:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise SpecError(f"invalid TOML: {e}") from e
    _check_keys("root", data, {"name", "question", "scene", "params", "run"})

    name = data.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise SpecError("name must be lowercase letters, digits or _")

    scene = SCENE_DEFAULTS | data.get("scene", {})
    _check_keys("scene", scene, SCENE_KEYS)
    presets = {p["id"] for p in providers.list_presets()}
    if "preset" not in scene:
        raise SpecError("[scene] preset is required")
    for preset in _as_list(scene["preset"]):
        if preset not in presets:
            raise SpecError(f"[scene] unknown preset {preset!r}; available: {', '.join(sorted(presets))}")

    params = data.get("params", {})
    specs = {s["name"]: s for s in providers.param_specs()}
    for pname, values in params.items():
        spec = specs.get(pname)
        if spec is None:
            raise SpecError(f"[params] unknown param {pname!r}; available: {', '.join(sorted(specs))}")
        for v in _as_list(values):
            if not isinstance(v, (int, float)) or not spec["min"] <= v <= spec["max"]:
                raise SpecError(f"[params] {pname}={v!r} must be a number in [{spec['min']}, {spec['max']}]")

    run = RUN_DEFAULTS | data.get("run", {})
    _check_keys("run", run, {"ignite", "max_time", "speed", "max_frames"})
    ignite = run.get("ignite")
    if not isinstance(ignite, list) or not ignite or not all(
        isinstance(p, list) and len(p) == 2 and all(isinstance(c, (int, float)) for c in p) for p in ignite
    ):
        raise SpecError("[run] ignite must be a non-empty list of [x, y] points in meters")
    if not isinstance(run.get("max_time"), (int, float)) or run["max_time"] <= 0:
        raise SpecError("[run] max_time (simulated seconds) must be positive")
    if run["speed"] not in SPEEDS:
        raise SpecError(f"[run] speed must be one of {SPEEDS}")

    return Experiment(
        name=name,
        question=str(data.get("question", "")),
        scene=scene,
        params=params,
        ignite=[(float(x), float(y)) for x, y in ignite],
        max_time=float(run["max_time"]),
        speed=int(run["speed"]),
        max_frames=int(run["max_frames"]),
        source=text,
        runs=_expand(scene, params),
    )


def load(path: Path) -> Experiment:
    try:
        return parse(path.read_text(encoding="utf-8"), str(path))
    except SpecError as e:
        raise SpecError(f"{path}: {e}") from e
