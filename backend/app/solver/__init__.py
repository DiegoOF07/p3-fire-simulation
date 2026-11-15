from app.solver.params import param_specs
from app.solver.simulation import FireSimulation

# Internal steps per frame at ×1 (dt ≈ 0.24 s with defaults); tuned with `pnpm bench`.
BASE_STEPS = 4

create_simulation = FireSimulation

__all__ = ["BASE_STEPS", "create_simulation", "param_specs"]
