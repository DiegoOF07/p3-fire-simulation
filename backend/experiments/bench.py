from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from app import providers
from app.api.ws import FPS
from app.contracts import Scene
from app.protocol import HEADER_SIZE, SPEEDS
from app.session import Session
from experiments.summary import write_rows

RESULTS = Path(__file__).parent / "results" / "bench.csv"


def flat_scene(n: int, cell_size: float = 1.0) -> Scene:
    return Scene(np.zeros((n, n), np.float32), cell_size, np.zeros((0, 4), np.float32))


def measure(n: int, speed: int, frames: int = 30, warmup: int = 5) -> dict[str, Any]:
    """Times the full live path: solver steps, quantization and packing."""
    scene = flat_scene(n)
    session = Session(scene, speed=speed)  # type: ignore[arg-type]
    session.ignite(scene.width / 2, scene.depth / 2)
    session.apply_pending()
    for _ in range(warmup):
        session.advance()
    samples = []
    for _ in range(frames):
        started = time.perf_counter()
        session.advance()
        samples.append(time.perf_counter() - started)
    ms = statistics.median(samples) * 1000
    kb = (HEADER_SIZE + 2 * n * n) / 1024
    return {
        "grid": f"{n}x{n}",
        "speed": speed,
        "steps_per_frame": providers.BASE_STEPS * speed,
        "ms_per_frame": round(ms, 2),
        "max_fps": round(1000 / ms, 1) if ms else float("inf"),
        "frame_kb": round(kb, 1),
        "mb_per_s": round(kb * FPS / 1024, 2),
        "ok": ms <= 1000 / FPS,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure frame cost per grid size and speed.")
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 200, 300, 400])
    parser.add_argument("--frames", type=int, default=30)
    args = parser.parse_args(argv)

    rows = [measure(n, s, args.frames) for n in args.sizes for s in SPEEDS]
    print(f"target {FPS} FPS -> {1000 / FPS:.0f} ms per frame, BASE_STEPS={providers.BASE_STEPS}")
    print(f"{'grid':>9} {'speed':>5} {'ms/frame':>9} {'max fps':>8} {'KB/frame':>9} {'MB/s':>6}  ok")
    for r in rows:
        print(f"{r['grid']:>9} {r['speed']:>5} {r['ms_per_frame']:>9} {r['max_fps']:>8} "
              f"{r['frame_kb']:>9} {r['mb_per_s']:>6}  {'yes' if r['ok'] else 'NO'}")
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    write_rows(RESULTS, rows)
    print(f"saved {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
