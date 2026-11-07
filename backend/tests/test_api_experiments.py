import csv

import pytest

from experiments import bench, summary
from experiments.run import main, run_experiment
from experiments.spec import SpecError, parse

SPEC = """
name = "prueba"
question = "q"
[scene]
preset = "flat"
density = [0.2, 0.5]
seed = [0, 1]
[params]
spread_speed = 2.0
[run]
ignite = [[100, 100]]
max_time = 5
"""


def test_sweeps_expand_to_cartesian_product():
    exp = parse(SPEC)
    assert len(exp.runs) == 4
    assert exp.runs[0].varied == {"scene.density": 0.2, "scene.seed": 0}
    assert exp.runs[3].scene == {"preset": "flat", "density": 0.5, "seed": 1}
    assert exp.runs[3].params == {"spread_speed": 2.0}


def spec_with(name='"x"', scene='preset = "flat"', params="", run="ignite = [[1, 1]]\nmax_time = 5"):
    return f"name = {name}\n[scene]\n{scene}\n[params]\n{params}\n[run]\n{run}\n"


@pytest.mark.parametrize("text, fragment", [
    (spec_with(name='"Bad Name"'), "name"),
    (spec_with(scene='preset = "nope"'), "unknown preset"),
    (spec_with(scene='preset = "flat"\nheight = 3'), "unknown keys"),
    (spec_with(params="nope = 1"), "unknown param"),
    (spec_with(params="spread_speed = 999"), "must be a number"),
    (spec_with(run="ignite = []\nmax_time = 5"), "ignite"),
    (spec_with(run="ignite = [[1, 1]]"), "max_time"),
    (spec_with(run="ignite = [[1, 1]]\nmax_time = 5\nspeed = 3"), "speed"),
    ("name = ", "invalid TOML"),
])
def test_invalid_specs(text, fragment):
    with pytest.raises(SpecError, match=fragment):
        parse(text)


def test_minimal_spec_is_valid():
    assert len(parse(spec_with()).runs) == 1


def test_run_writes_histories_and_summaries(tmp_path):
    exp = parse(SPEC)
    rows = run_experiment(exp, tmp_path)
    out = tmp_path / "prueba"
    assert sorted(p.name for p in out.glob("*.csv")) == ["000.csv", "001.csv", "002.csv", "003.csv", "summary.csv"]
    assert (out / "spec.toml").read_text(encoding="utf-8") == SPEC
    assert all(r["stop"] == "max_time" and r["t_end"] >= 5 for r in rows)
    with (out / "000.csv").open(encoding="utf-8") as f:
        assert next(csv.reader(f))[:2] == ["frame", "t"]

    md = summary.build(tmp_path).read_text(encoding="utf-8")
    assert "## prueba" in md and "scene.density" in md
    with (tmp_path / "summary.csv").open(encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 4


def test_cli_dry_run(tmp_path, capsys):
    spec = tmp_path / "x.toml"
    spec.write_text(SPEC, encoding="utf-8")
    assert main([str(spec), "--dry-run", "--out", str(tmp_path)]) == 0
    assert "prueba: 4 runs" in capsys.readouterr().out
    assert not (tmp_path / "prueba").exists()


def test_cli_reports_bad_spec(tmp_path, capsys):
    spec = tmp_path / "x.toml"
    spec.write_text('name = "x"', encoding="utf-8")
    assert main([str(spec)]) == 1
    assert "error" in capsys.readouterr().err


def test_bench_measures_small_grid():
    row = bench.measure(50, 1, frames=3, warmup=1)
    assert row["grid"] == "50x50" and row["ms_per_frame"] > 0
