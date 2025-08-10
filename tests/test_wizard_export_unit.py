from __future__ import annotations

import json
import os
import tempfile

from iop_flow import formulas as F
from iop_flow.api import run_all
from iop_flow.schemas import AirConditions, Engine
from iop_flow.io_json import write_session, read_session

from iop_flow_gui.wizard.state import WizardState, set_geometry_from_ui


def _state_with_min_data() -> WizardState:
    s = WizardState()
    s.meta["project_name"] = "Rpt"
    s.meta["client"] = "Unit"
    s.air_dp_ref_inH2O = 28.0
    s.air = AirConditions(p_tot=101325.0, T=F.C_to_K(20.0), RH=0.0)
    s.engine = Engine(displ_L=2.0, cylinders=4, ve=0.95)
    set_geometry_from_ui(
        s,
        bore_mm=86.0,
        valve_int_mm=32.0,
        valve_exh_mm=28.0,
        throat_mm=7.5,
        stem_mm=5.0,
        seat_angle_deg=45.0,
        seat_width_mm=2.0,
        port_volume_cc=180.0,
        port_length_mm=100.0,
    )
    s.lifts_intake_mm = [1.0, 2.0]
    s.measure_intake = [
        {"lift_mm": 1.0, "q_cfm": 100.0, "dp_inH2O": 28.0},
        {"lift_mm": 2.0, "q_cfm": 160.0, "dp_inH2O": 28.0},
    ]
    return s


def test_export_json_and_csv_like() -> None:
    s = _state_with_min_data()
    session = s.build_session_for_run_all()
    out = run_all(session, dp_ref_inH2O=s.air_dp_ref_inH2O)

    with tempfile.TemporaryDirectory() as tmp:
        session_path = os.path.join(tmp, "session.json")
        results_path = os.path.join(tmp, "results.json")
        csv_path = os.path.join(tmp, "intake.csv")

        # Session JSON via io_json helpers (roundtrip)
        write_session(session_path, session)
        s_loaded = read_session(session_path)
        assert s_loaded.geom.throat_m > 0
        assert s_loaded.engine.displ_L > 0

        # Results JSON
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        with open(results_path, "r", encoding="utf-8") as f:
            data2 = json.load(f)
            assert "series" in data2 and "intake" in data2["series"]

        # CSV (intake only)
        series_int = out["series"]["intake"]
        headers = ["lift_m", "q_m3s_ref", "A_ref_key", "Cd_ref", "V_ref", "Mach_ref", "SR"]
        # Use utf-8-sig to include BOM for Excel friendliness
        with open(csv_path, "w", encoding="utf-8-sig") as f:
            f.write(",".join(headers) + "\n")
            for r in series_int:
                row = [
                    r.get("lift_m"),
                    r.get("q_m3s_ref"),
                    r.get("A_ref_key"),
                    r.get("Cd_ref"),
                    r.get("V_ref"),
                    r.get("Mach_ref"),
                    r.get("SR", ""),
                ]
                f.write(",".join(str(x) for x in row) + "\n")
        # Verify BOM present
        with open(csv_path, "rb") as fb:
            start = fb.read(3)
            assert start == b"\xef\xbb\xbf"
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip()]
            assert lines[0].startswith("lift_m,q_m3s_ref,A_ref_key,Cd_ref,V_ref,Mach_ref,SR")
            assert len(lines) > 1
