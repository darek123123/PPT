from pathlib import Path
from statistics import mean

from iop_flow.io_json import read_session
from iop_flow.api import run_all, run_compare


DATA = Path(__file__).resolve().parent / "data"


def test_e2e_run_all_intake_only() -> None:
    s = read_session(DATA / "session_intake_only.json")
    out = run_all(s)
    assert "series" in out and "engine" in out
    assert isinstance(out["series"]["intake"], list)
    assert out["series"]["exhaust"] == []


def test_e2e_run_all_intake_exhaust_ei_rows() -> None:
    s = read_session(DATA / "session_intake_exhaust.json")
    out = run_all(s)
    ei = out["series"]["ei"]
    assert isinstance(ei, list) and len(ei) > 0
    # common lifts: [1,2,3,4,5] -> 5 rows
    assert len(ei) == 5


def test_e2e_compare_before_after_delta_pct() -> None:
    before = read_session(DATA / "before.json")
    after = read_session(DATA / "after.json")
    diff = run_compare(before, after, keys=("q_m3s_ref", "Cd_ref"))
    rows = diff["intake"]["diffs"]["q_m3s_ref"]
    # average delta should be ~ +10% with small tolerance
    avg = mean(r["delta_pct"] for r in rows)
    assert 9.0 <= avg <= 11.0
