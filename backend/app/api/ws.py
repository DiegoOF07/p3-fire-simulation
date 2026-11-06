from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.session import Session, sessions
from app.store import scenes

FPS = 20

router = APIRouter()


async def _stream(ws: WebSocket, session: Session) -> None:
    while session.state == "running":
        started = time.perf_counter()
        frame = session.advance()
        await ws.send_bytes(frame)
        await ws.send_json({"type": "metrics", "frame": session.frame, "metrics": session.sim.metrics()})
        if session.state == "finished":
            await _send_state(ws, session)
            return
        await asyncio.sleep(max(0.0, 1 / FPS - (time.perf_counter() - started)))


async def _send_state(ws: WebSocket, session: Session) -> None:
    await ws.send_json({"type": "state", "state": session.state, "speed": session.speed})


async def _error(ws: WebSocket, message: str) -> None:
    await ws.send_json({"type": "error", "message": message})


@router.websocket("/ws/sim")
async def sim_socket(ws: WebSocket) -> None:
    await ws.accept()
    session: Session | None = None
    streamer: asyncio.Task | None = None
    try:
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type")
            if kind == "start":
                scene = scenes.get(msg.get("scene_id", ""))
                if scene is None:
                    await _error(ws, "unknown scene_id")
                    continue
                if streamer:
                    streamer.cancel()
                session = Session(scene, msg.get("params", {}))
                sessions[session.id] = session
                await ws.send_json({"type": "session", "id": session.id})
                await _send_state(ws, session)
                streamer = asyncio.create_task(_stream(ws, session))
            elif session is None:
                await _error(ws, "send start first")
            elif kind == "ignite":
                try:
                    session.ignite(float(msg["x"]), float(msg["y"]))
                except (KeyError, TypeError, ValueError):
                    await _error(ws, "ignite needs numeric x and y")
            else:
                # pause, resume, reset, set_param, set_speed arrive in Phase 1.
                await _error(ws, f"unsupported message type {kind!r}")
    except WebSocketDisconnect:
        pass
    finally:
        if streamer:
            streamer.cancel()
