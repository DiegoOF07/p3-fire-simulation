from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.session import Rendered, Session, sessions
from app.store import scenes

FPS = 20

log = logging.getLogger(__name__)
router = APIRouter()


class Channel:
    """Serializes sends from the handler and the runner."""

    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self._lock = asyncio.Lock()

    async def json(self, data: dict) -> None:
        async with self._lock:
            await self.ws.send_json(data)

    async def bytes(self, data: bytes) -> None:
        async with self._lock:
            await self.ws.send_bytes(data)

    async def state(self, s: Session) -> None:
        await self.json({"type": "state", "state": s.state, "speed": s.speed})

    async def error(self, message: str) -> None:
        await self.json({"type": "error", "message": message})


class Runner:
    """Frame loop of one session. The solver runs in a worker thread; commands queue between frames."""

    def __init__(self, ch: Channel, session: Session) -> None:
        self.ch = ch
        self.session = session
        self._wake = asyncio.Event()
        self._task = asyncio.create_task(self._run())

    def poke(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._task.cancel()

    async def _run(self) -> None:
        s = self.session
        while True:
            if s.state == "running":
                started = time.perf_counter()
                s.apply_pending()
                if not await self._send_frame(s.advance):
                    continue
                if s.state == "finished":
                    await self.ch.state(s)
                    continue
                await asyncio.sleep(max(0.0, 1 / FPS - (time.perf_counter() - started)))
            elif s.has_pending:
                # Paused or finished: show ignitions without stepping.
                s.apply_pending()
                await self._send_frame(s.render)
            else:
                self._wake.clear()
                await self._wake.wait()

    async def _send_frame(self, produce: Callable[[], Rendered]) -> bool:
        s = self.session
        try:
            frame, metrics, sim_finished = await asyncio.to_thread(produce)
        except Exception as e:
            log.exception("simulation failed")
            s.pause()
            await self.ch.error(f"simulation failed: {e}")
            await self.ch.state(s)
            return False
        s.settle(sim_finished)
        await self.ch.bytes(frame)
        await self.ch.json({"type": "metrics", "frame": s.frame, "metrics": metrics})
        return True


async def _launch(ch: Channel, old: Runner | None, session: Session) -> Runner:
    if old:
        old.stop()
    sessions.put(session.id, session)
    await ch.json({"type": "session", "id": session.id})
    await ch.state(session)
    return Runner(ch, session)


async def _handle(ch: Channel, runner: Runner | None, msg: dict) -> Runner | None:
    kind = msg["type"]
    if kind == "start":
        scene = scenes.get(str(msg["scene_id"]))
        if scene is None:
            raise ValueError("unknown scene_id")
        params = msg.get("params") or {}
        if not isinstance(params, dict):
            raise ValueError("params must be an object")
        return await _launch(ch, runner, Session(scene, params))
    if runner is None:
        raise ValueError("send start first")

    s = runner.session
    before = (s.state, s.speed)
    match kind:
        case "pause":
            s.pause()
        case "resume":
            s.resume()
        case "reset":
            return await _launch(ch, runner, s.restart())
        case "ignite":
            s.ignite(float(msg["x"]), float(msg["y"]))
        case "set_param":
            s.set_param(str(msg["name"]), float(msg["value"]))
        case "set_speed":
            s.set_speed(int(msg["speed"]))
        case _:
            raise ValueError(f"unknown message type {kind!r}")
    runner.poke()
    if (s.state, s.speed) != before:
        await ch.state(s)
    return runner


@router.websocket("/ws/sim")
async def sim_socket(ws: WebSocket) -> None:
    await ws.accept()
    ch = Channel(ws)
    runner: Runner | None = None
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
                if not isinstance(msg, dict):
                    raise ValueError("message must be a JSON object")
                runner = await _handle(ch, runner, msg)
            except KeyError as e:
                await ch.error(f"missing field {e}")
            except (TypeError, ValueError) as e:
                await ch.error(str(e))
    except WebSocketDisconnect:
        pass
    finally:
        if runner:
            runner.stop()
