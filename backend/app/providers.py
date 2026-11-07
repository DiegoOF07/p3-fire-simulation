from __future__ import annotations

from app.contracts import BuildScene, SimFactory
from app.mock import scenes as scene_impl
from app.mock import simulation as sim_impl

# Swap these imports for app.solver / app.scenes when they're ready.
list_presets = scene_impl.list_presets
build_scene: BuildScene = scene_impl.build_scene
param_specs = sim_impl.param_specs
create_simulation: SimFactory = sim_impl.MockSimulation

# Solver steps per frame at ×1.
BASE_STEPS = 1
