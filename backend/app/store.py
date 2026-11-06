from __future__ import annotations

import uuid
from collections import OrderedDict

from app.contracts import Scene

MAX_SCENES = 16


class SceneStore:
    def __init__(self, capacity: int = MAX_SCENES) -> None:
        self._scenes: OrderedDict[str, Scene] = OrderedDict()
        self._capacity = capacity

    def add(self, scene: Scene) -> str:
        scene_id = uuid.uuid4().hex[:12]
        self._scenes[scene_id] = scene
        if len(self._scenes) > self._capacity:
            self._scenes.popitem(last=False)
        return scene_id

    def get(self, scene_id: str) -> Scene | None:
        scene = self._scenes.get(scene_id)
        if scene is not None:
            self._scenes.move_to_end(scene_id)
        return scene


scenes = SceneStore()
