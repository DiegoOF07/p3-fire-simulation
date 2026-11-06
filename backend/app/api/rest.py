from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app import providers
from app.contracts import ParamSpec, PresetInfo, Scene
from app.store import scenes

router = APIRouter(prefix="/api")


class BuildRequest(BaseModel):
    preset: str
    density: float = Field(1.0, ge=0)
    seed: int = 0


class SceneMeta(BaseModel):
    id: str
    nx: int
    ny: int
    cell_size: float
    n_trees: int


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/params")
def params() -> list[ParamSpec]:
    return providers.param_specs()


@router.get("/scenes")
def list_scenes() -> list[PresetInfo]:
    return providers.list_presets()


@router.post("/scenes/build")
def build_scene(req: BuildRequest) -> SceneMeta:
    try:
        scene = providers.build_scene(req.preset, req.density, req.seed)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    scene_id = scenes.add(scene)
    return SceneMeta(id=scene_id, nx=scene.nx, ny=scene.ny,
                     cell_size=scene.cell_size, n_trees=len(scene.trees))


def _scene_or_404(scene_id: str) -> Scene:
    scene = scenes.get(scene_id)
    if scene is None:
        raise HTTPException(404, f"scene {scene_id!r} not found")
    return scene


def _f32(arr: np.ndarray) -> Response:
    return Response(arr.astype("<f4").tobytes(), media_type="application/octet-stream")


@router.get("/scenes/{scene_id}/heightmap")
def heightmap(scene_id: str) -> Response:
    return _f32(_scene_or_404(scene_id).heightmap)


@router.get("/scenes/{scene_id}/trees")
def trees(scene_id: str) -> Response:
    return _f32(_scene_or_404(scene_id).trees)
