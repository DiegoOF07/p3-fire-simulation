from __future__ import annotations

import uuid

from app import providers
from app.contracts import Scene, Simulation, default_params
from app.protocol import SimState, Speed, pack_frame

IGNITION_RADIUS = 3.0  # m


class Session:
    def __init__(self, scene: Scene, params: dict[str, float]) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.scene = scene
        self.params = default_params(providers.param_specs()) | params
        self.sim: Simulation = providers.create_simulation(scene, self.params)
        self.frame = 0
        self.state: SimState = "running"
        self.speed: Speed = 1

    def ignite(self, x: float, y: float) -> None:
        self.sim.ignite(x, y, IGNITION_RADIUS)

    def advance(self) -> bytes:
        """Steps one frame and returns it packed."""
        self.sim.step(self.speed)
        self.frame += 1
        if self.sim.finished():
            self.state = "finished"
        T, beta = self.sim.fields_uint8()
        return pack_frame(self.frame, self.sim.metrics()["t"], T, beta)


sessions: dict[str, Session] = {}
