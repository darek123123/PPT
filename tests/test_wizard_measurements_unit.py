from __future__ import annotations

from iop_flow_gui.wizard.state import WizardState, parse_rows, set_geometry_from_ui
from iop_flow import formulas as F
from iop_flow.schemas import AirConditions, Engine
from iop_flow.api import run_all


def test_parse_rows_variants() -> None:
    rows = parse_rows("2,0 180 28")
    assert rows == [(2.0, 180.0, 28.0, None)]
    rows2 = parse_rows("3.5; 220; ; 900")
    assert rows2 == [(3.5, 220.0, None, 900.0)]


def _minimal_state_with_steps_1_to_5() -> WizardState:
    s = WizardState()
    # Step 1 meta
    s.meta["project_name"] = "X"
    s.meta["client"] = "Y"
    # Step 2 air
    s.air_dp_ref_inH2O = 28.0
    s.air = AirConditions(p_tot=101325.0, T=F.C_to_K(20.0), RH=0.0)
    # Step 3 engine
    s.engine = Engine(displ_L=2.0, cylinders=4, ve=0.9)
    s.engine_target_rpm = 6000
    # Step 4 geometry
    set_geometry_from_ui(
        s,
        bore_mm=86.0,
        valve_int_mm=32.0,
        valve_exh_mm=28.0,
        throat_mm=7.0,
        stem_mm=5.0,
        seat_angle_deg=45.0,
        seat_width_mm=2.0,
        port_volume_cc=180.0,
        port_length_mm=100.0,
    )
    # Step 5 plan (minimal)
    s.lifts_intake_mm = [1.0, 2.0]
    s.lifts_exhaust_mm = []
    return s


def test_session_build_includes_intake_series() -> None:
    s = _minimal_state_with_steps_1_to_5()
    s.measure_intake = [
        {"lift_mm": 1.0, "q_cfm": 100.0, "dp_inH2O": 28.0},
        {"lift_mm": 2.0, "q_cfm": 150.0},  # no dp -> treat as ref in core
    ]
    sess = s.build_session_from_wizard_for_compute()
    assert len(sess.lifts.intake) == 2
    assert sess.lifts.exhaust == []


def test_run_all_has_required_keys_on_intake_points() -> None:
    s = _minimal_state_with_steps_1_to_5()
    s.measure_intake = [
        {"lift_mm": 1.0, "q_cfm": 100.0, "dp_inH2O": 28.0},
        {"lift_mm": 2.0, "q_cfm": 150.0},
    ]
    session = s.build_session_from_wizard_for_compute()
    result = run_all(
        session, dp_ref_inH2O=s.air_dp_ref_inH2O, a_ref_mode="eff", eff_mode="smoothmin"
    )
    intake = result["series"]["intake"]
    assert len(intake) == 2
    for pt in intake:
        assert "Cd_ref" in pt and pt["Cd_ref"] is not None
        assert "q_m3s_ref" in pt and pt["q_m3s_ref"] is not None
