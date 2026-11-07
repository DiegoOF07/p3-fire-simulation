from __future__ import annotations

import csv
import io

import numpy as np
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app import providers
from app.contracts import METRIC_KEYS, ParamSpec, PresetInfo, Scene
from app.session import sessions
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
    return _meta(scenes.add(scene), scene)


def _meta(scene_id: str, scene: Scene) -> SceneMeta:
    return SceneMeta(id=scene_id, nx=scene.nx, ny=scene.ny,
                     cell_size=scene.cell_size, n_trees=len(scene.trees))


def _scene_or_404(scene_id: str) -> Scene:
    scene = scenes.get(scene_id)
    if scene is None:
        raise HTTPException(404, f"scene {scene_id!r} not found")
    return scene


@router.get("/scenes/{scene_id}")
def scene_meta(scene_id: str) -> SceneMeta:
    return _meta(scene_id, _scene_or_404(scene_id))


def _f32(arr: np.ndarray) -> Response:
    return Response(arr.astype("<f4").tobytes(), media_type="application/octet-stream")


@router.get("/scenes/{scene_id}/heightmap")
def heightmap(scene_id: str) -> Response:
    return _f32(_scene_or_404(scene_id).heightmap)


@router.get("/scenes/{scene_id}/trees")
def trees(scene_id: str) -> Response:
    return _f32(_scene_or_404(scene_id).trees)


@router.get("/sessions/{session_id}/export.csv")
def export_csv(session_id: str) -> Response:
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(404, f"session {session_id!r} not found")
    history = session.sim.history()
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["frame", *METRIC_KEYS])
    writer.writerows([i + 1, *row] for i, row in enumerate(zip(*(history[k] for k in METRIC_KEYS))))
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="session-{session_id}.csv"'})
