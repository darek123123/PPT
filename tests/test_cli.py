import json
import os
import sys
import subprocess
from pathlib import Path
from iop_flow.schemas import AirConditions, Engine, Geometry, LiftPoint, FlowSeries, Session
from iop_flow.io_json import write_session


def _make_session(tmp: Path) -> Path:
    air = AirConditions(p_tot=101325.0, T=293.15, RH=0.0)
    eng = Engine(displ_L=2.0, cylinders=4, ve=0.95)
    geom = Geometry(
        bore_m=0.086,
        valve_int_m=0.046,
        valve_exh_m=0.040,
        throat_m=0.034,
        stem_m=0.007,
        port_volume_cc=180.0,
        port_length_m=0.110,
        seat_angle_deg=45.0,
        seat_width_m=0.0015,
    )
    intake = [
        LiftPoint(lift_mm=1.0, q_cfm=120.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=2.0, q_cfm=175.0, dp_inH2O=28.0),
    ]
    fs = FlowSeries(intake=intake, exhaust=[])
    s = Session(
        meta={"project": "cli"}, mode="baseline", air=air, engine=eng, geom=geom, lifts=fs, csa=None
    )
    p = tmp / "sess.json"
    write_session(p, s)
    return p


def test_cli_run_produces_output_json(tmp_path: Path) -> None:
    sess = _make_session(tmp_path)
    out = tmp_path / "res.json"
    cmd = [sys.executable, "-m", "iop_flow.cli", "run", "--in", str(sess), "--out", str(out)]
    env = dict(**os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    subprocess.run(cmd, check=True, env=env)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "series" in data and "intake" in data["series"]


def test_cli_schema_writes_example(tmp_path: Path) -> None:
    out = tmp_path / "example.json"
    cmd = [sys.executable, "-m", "iop_flow.cli", "schema", "--out", str(out)]
    env = dict(**os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    subprocess.run(cmd, check=True, env=env)
    assert out.exists()
