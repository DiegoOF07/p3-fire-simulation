from __future__ import annotations

import importlib
import os
from typing import Callable

from app.contracts import BuildScene, ParamSpec, PresetInfo, SimFactory

# Simulation module exposes: param_specs(), create_simulation(scene, params), optional BASE_STEPS.
# Scenes module exposes: list_presets(), build_scene(preset, density, seed).
# Set them to app.mock.simulation / app.mock.scenes to run without the real solver.
SIM_MODULE = os.environ.get("FIRE_SIM_MODULE", "app.solver")
SCENES_MODULE = os.environ.get("FIRE_SCENES_MODULE", "app.scenes")

_sim = importlib.import_module(SIM_MODULE)
_scenes = importlib.import_module(SCENES_MODULE)

list_presets: Callable[[], list[PresetInfo]] = _scenes.list_presets
build_scene: BuildScene = _scenes.build_scene
param_specs: Callable[[], list[ParamSpec]] = _sim.param_specs
create_simulation: SimFactory = _sim.create_simulation

# Solver steps per frame at ×1.
BASE_STEPS: int = getattr(_sim, "BASE_STEPS", 1)
