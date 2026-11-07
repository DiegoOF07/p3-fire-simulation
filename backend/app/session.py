from __future__ import annotations

from typing import Callable

from app import providers
from app.contracts import Metrics, ParamSpec, Scene, Simulation, default_params
from app.protocol import SPEEDS, SimState, Speed, pack_frame
from app.store import LRUStore, new_id

IGNITION_RADIUS = 3.0  # m

Command = Callable[[Simulation], None]
Rendered = tuple[bytes, Metrics, bool]  # frame, metrics, sim finished


def _specs() -> dict[str, ParamSpec]:
    return {s["name"]: s for s in providers.param_specs()}


def _checked(spec: ParamSpec, value: float) -> float:
    value = float(value)
    if not spec["min"] <= value <= spec["max"]:
        raise ValueError(f"{spec['name']} must be in [{spec['min']}, {spec['max']}]")
    return value


class Session:
    """Simulation state between frames. Only advance/render run off the event loop."""

    def __init__(self, scene: Scene, params: dict[str, float] | None = None, speed: Speed = 1) -> None:
        specs = _specs()
        for name, value in (params or {}).items():
            if name not in specs:
                raise ValueError(f"unknown param {name!r}")
            _checked(specs[name], value)
        self.id = new_id()
        self.scene = scene
        self.params = default_params(list(specs.values())) | {k: float(v) for k, v in (params or {}).items()}
        self.sim: Simulation = providers.create_simulation(scene, dict(self.params))
        self.frame = 0
        self.state: SimState = "running"
        self.speed: Speed = speed
        self._pending: list[Command] = []

    def restart(self) -> Session:
        return Session(self.scene, self.params, self.speed)

    def pause(self) -> None:
        if self.state == "running":
            self.state = "paused"

    def resume(self) -> None:
        if self.state == "paused":
            self.state = "running"

    def set_speed(self, speed: int) -> None:
        if speed not in SPEEDS:
            raise ValueError(f"speed must be one of {SPEEDS}")
        self.speed = speed  # type: ignore[assignment]

    def ignite(self, x: float, y: float) -> None:
        if not (0 <= x < self.scene.width and 0 <= y < self.scene.depth):
            raise ValueError("ignition point outside the scene")
        self._pending.append(lambda sim: sim.ignite(x, y, IGNITION_RADIUS))
        if self.state == "finished":
            self.state = "running"

    def set_param(self, name: str, value: float) -> None:
        spec = _specs().get(name)
        if spec is None:
            raise ValueError(f"unknown param {name!r}")
        if not spec["live"]:
            raise ValueError(f"{name} can only be set before start")
        value = _checked(spec, value)
        self.params[name] = value
        self._pending.append(lambda sim: sim.set_param(name, value))

    @property
    def has_pending(self) -> bool:
        return bool(self._pending)

    def apply_pending(self) -> None:
        """Call only while no advance/render is running."""
        pending, self._pending = self._pending, []
        for cmd in pending:
            cmd(self.sim)

    def advance(self) -> Rendered:
        self.step()
        return self.render()

    def step(self) -> None:
        """One frame of solver steps, without rendering (headless runs)."""
        self.sim.step(providers.BASE_STEPS * self.speed)
        self.frame += 1

    def render(self) -> Rendered:
        T, beta = self.sim.fields_uint8()
        metrics = self.sim.metrics()
        return pack_frame(self.frame, metrics["t"], T, beta), metrics, self.sim.finished()

    def settle(self, sim_finished: bool) -> None:
        """Applies a frame's finished flag back on the event loop."""
        if sim_finished and self.state == "running" and not self._pending:
            self.state = "finished"


# Kept after the socket closes so their CSV can still be exported.
sessions: LRUStore[Session] = LRUStore(32)
