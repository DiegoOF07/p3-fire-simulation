from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

# Columns shown in the markdown table, after the swept ones.
MD_COLUMNS = ["stop", "t_end", "burned_area_frac", "burned_trees_frac", "front_speed_mean", "T_max_peak"]


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    cols: list[str] = []
    for row in rows:
        cols += [k for k in row if k not in cols]
    return cols


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_columns(rows))
        writer.writeheader()
        writer.writerows(rows)


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _fmt(value: str) -> str:
    try:
        number = float(value)
    except ValueError:
        return value
    return f"{number:.3g}" if abs(number) < 1000 else f"{number:.0f}"


def _markdown(experiment: str, rows: list[dict[str, str]]) -> str:
    swept = [c for c in rows[0] if "." in c]
    cols = ["run", *swept, *[c for c in MD_COLUMNS if c in rows[0]]]
    lines = [f"## {experiment}", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(r["run"] if c == "run" else _fmt(r.get(c, "")) for c in cols) + " |" for r in rows]
    return "\n".join(lines)


def build(results_dir: Path) -> Path:
    """Merges every results/<experiment>/summary.csv into summary.csv and summary.md."""
    per_exp = {p.parent.name: _read(p) for p in sorted(results_dir.glob("*/summary.csv"))}
    all_rows = [r for rows in per_exp.values() for r in rows]
    if all_rows:
        write_rows(results_dir / "summary.csv", all_rows)
    md = ["# Resumen de experimentos", ""]
    md += [_markdown(name, rows) + "\n" for name, rows in per_exp.items() if rows]
    (results_dir / "summary.md").write_text("\n".join(md), encoding="utf-8")
    return results_dir / "summary.md"


if __name__ == "__main__":
    from experiments.run import RESULTS_DIR

    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else RESULTS_DIR))
