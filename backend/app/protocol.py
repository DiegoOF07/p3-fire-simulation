from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Literal, TypedDict

import numpy as np

from app.contracts import Metrics

PROTOCOL_VERSION = 1
HEADER = struct.Struct("<IfHHB3x")
HEADER_SIZE = HEADER.size


@dataclass
class Frame:
    frame: int
    t: float
    T: np.ndarray
    beta: np.ndarray
    version: int = PROTOCOL_VERSION


def pack_frame(frame: int, t: float, T: np.ndarray, beta: np.ndarray) -> bytes:
    if T.dtype != np.uint8 or beta.dtype != np.uint8:
        raise TypeError("T and beta must be uint8")
    if T.ndim != 2 or T.shape != beta.shape:
        raise ValueError(f"T and beta must share a 2D shape, got {T.shape} and {beta.shape}")
    ny, nx = T.shape
    if nx > 0xFFFF or ny > 0xFFFF:
        raise ValueError("grid too large for uint16 dimensions")
    header = HEADER.pack(frame & 0xFFFFFFFF, t, nx, ny, PROTOCOL_VERSION)
    return b"".join((header, np.ascontiguousarray(T).data, np.ascontiguousarray(beta).data))


def unpack_frame(data: bytes) -> Frame:
    if len(data) < HEADER_SIZE:
        raise ValueError("buffer shorter than header")
    frame, t, nx, ny, version = HEADER.unpack_from(data)
    if version != PROTOCOL_VERSION:
        raise ValueError(f"unsupported protocol version {version}")
    n = nx * ny
    if len(data) != HEADER_SIZE + 2 * n:
        raise ValueError(f"expected {HEADER_SIZE + 2 * n} bytes, got {len(data)}")
    body = np.frombuffer(data, dtype=np.uint8, offset=HEADER_SIZE)
    return Frame(frame, t, body[:n].reshape(ny, nx), body[n:].reshape(ny, nx), version)


Speed = Literal[1, 5, 20]
SPEEDS: tuple[int, ...] = (1, 5, 20)
SimState = Literal["idle", "running", "paused", "finished"]


class StartMsg(TypedDict):
    type: Literal["start"]
    scene_id: str
    params: dict[str, float]


class PauseMsg(TypedDict):
    type: Literal["pause"]


class ResumeMsg(TypedDict):
    type: Literal["resume"]


class ResetMsg(TypedDict):
    type: Literal["reset"]


class IgniteMsg(TypedDict):
    type: Literal["ignite"]
    x: float  # m
    y: float  # m


class SetParamMsg(TypedDict):
    type: Literal["set_param"]
    name: str
    value: float


class SetSpeedMsg(TypedDict):
    type: Literal["set_speed"]
    speed: Speed


ClientMsg = StartMsg | PauseMsg | ResumeMsg | ResetMsg | IgniteMsg | SetParamMsg | SetSpeedMsg


class SessionMsg(TypedDict):
    type: Literal["session"]
    id: str  # for /api/sessions/{id}/export.csv


class MetricsMsg(TypedDict):
    type: Literal["metrics"]
    frame: int
    metrics: Metrics


class StateMsg(TypedDict):
    type: Literal["state"]
    state: SimState
    speed: Speed


class ErrorMsg(TypedDict):
    type: Literal["error"]
    message: str


ServerMsg = SessionMsg | MetricsMsg | StateMsg | ErrorMsg
