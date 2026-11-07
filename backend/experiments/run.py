from __future__ import annotations

import argparse
import csv
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from app import providers
from app.contracts import METRIC_KEYS
from app.session import Session
from experiments import summary
from experiments.spec import Experiment, RunConfig, SpecError, load

ROOT = Path(__file__).parent
SPECS_DIR = ROOT / "specs"
RESULTS_DIR = ROOT / "results"


def run_one(exp: Experiment, cfg: RunConfig) -> tuple[dict[str, Any], dict[str, list[float]]]:
    """Runs one configuration headless and returns (summary row, history)."""
    scene = providers.build_scene(cfg.scene["preset"], float(cfg.scene["density"]), int(cfg.scene["seed"]))
    session = Session(scene, cfg.params, speed=exp.speed)  # type: ignore[arg-type]
    for x, y in exp.ignite:
        session.ignite(x, y)
    session.apply_pending()

    started = time.perf_counter()
    reason = "max_frames"
    while session.frame < exp.max_frames:
        session.step()
        if session.sim.finished():
            reason = "finished"
            break
        if session.sim.metrics()["t"] >= exp.max_time:
            reason = "max_time"
            break
    wall = time.perf_counter() - started

    m = session.sim.metrics()
    history = session.sim.history()
    speeds = [v for v in history["front_speed"] if v > 0]
    n_trees = len(scene.trees)
    row: dict[str, Any] = {
        "experiment": exp.name,
        "run": f"{cfg.index:03d}",
        **cfg.varied,
        "stop": reason,
        "t_end": m["t"],
        "burned_area": m["burned_area"],
        "burned_area_frac": m["burned_area"] / (scene.width * scene.depth),
        "burned_trees": m["burned_trees"],
        "burned_trees_frac": m["burned_trees"] / n_trees if n_trees else 0.0,
        "front_speed_mean": sum(speeds) / len(speeds) if speeds else 0.0,
        "T_max_peak": max(history["T_max"], default=m["T_max"]),
        "frames": session.frame,
        "wall_s": round(wall, 3),
    }
    return row, history


def _write_history(path: Path, history: dict[str, list[float]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["frame", *METRIC_KEYS])
        writer.writerows([i + 1, *vals] for i, vals in enumerate(zip(*(history[k] for k in METRIC_KEYS))))


def _job(exp: Experiment, cfg: RunConfig, out_dir: Path) -> dict[str, Any]:
    row, history = run_one(exp, cfg)
    _write_history(out_dir / f"{cfg.index:03d}.csv", history)
    return row


def run_experiment(exp: Experiment, results_dir: Path = RESULTS_DIR, jobs: int = 1) -> list[dict[str, Any]]:
    out_dir = results_dir / exp.name
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    (out_dir / "spec.toml").write_text(exp.source, encoding="utf-8")

    if jobs > 1:
        with ProcessPoolExecutor(jobs) as pool:
            rows = list(pool.map(_job, [exp] * len(exp.runs), exp.runs, [out_dir] * len(exp.runs)))
    else:
        rows = []
        for cfg in exp.runs:
            rows.append(_job(exp, cfg, out_dir))
            print(f"  {exp.name} {cfg.index + 1}/{len(exp.runs)} {cfg.varied or ''}", flush=True)

    summary.write_rows(out_dir / "summary.csv", rows)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run fire experiments without the UI.")
    parser.add_argument("specs", nargs="*", type=Path, help="TOML specs (default: every file in experiments/specs)")
    parser.add_argument("--jobs", type=int, default=1, help="parallel processes")
    parser.add_argument("--out", type=Path, default=RESULTS_DIR, help="results folder")
    parser.add_argument("--dry-run", action="store_true", help="validate and list runs only")
    args = parser.parse_args(argv)

    paths = args.specs or sorted(SPECS_DIR.glob("*.toml"))
    if not paths:
        print(f"no specs found in {SPECS_DIR}", file=sys.stderr)
        return 1
    try:
        experiments = [load(p) for p in paths]
    except SpecError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    for exp in experiments:
        print(f"{exp.name}: {len(exp.runs)} runs")
        if args.dry_run:
            for cfg in exp.runs:
                print(f"  {cfg.index:03d} {cfg.varied}")
            continue
        run_experiment(exp, args.out, args.jobs)

    if not args.dry_run:
        table = summary.build(args.out)
        print(f"summary: {table}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
