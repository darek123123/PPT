from __future__ import annotations

from statistics import mean

from iop_flow import formulas as F
from iop_flow.api import run_all
from iop_flow.engine_link import mach_at_min_csa_for_series, rpm_from_csa_with_target
from iop_flow.schemas import AirConditions, Engine

from iop_flow_gui.wizard.state import WizardState, set_geometry_from_ui


def _base_state_with_intake(points: list[tuple[float, float, float | None]]) -> WizardState:
    s = WizardState()
    # minimal meta
    s.meta["project_name"] = "B4"
    s.meta["client"] = "Unit"
    # air
    s.air_dp_ref_inH2O = 28.0
    s.air = AirConditions(p_tot=101325.0, T=F.C_to_K(20.0), RH=0.0)
    # engine
    s.engine = Engine(displ_L=2.0, cylinders=4, ve=0.95)
    s.engine_target_rpm = 6000
    # geometry
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
    # plan (not strictly required by compute but keep consistent)
    s.lifts_intake_mm = sorted({round(p[0], 3) for p in points})
    # measurements (intake)
    s.measure_intake = [
        {"lift_mm": lift, "q_cfm": q, **({"dp_inH2O": dp} if dp is not None else {})}
        for (lift, q, dp) in points
    ]
    return s


def test_mach_at_min_csa_list() -> None:
    # intake points: (lift_mm, q_cfm, dp_inH2O)
    s = _base_state_with_intake([(1.0, 100.0, 28.0), (2.0, 160.0, 28.0), (3.0, 200.0, 28.0)])
    # set CSA min ~ 950 mm^2
    s.set_csa_from_ui(min_csa_mm2=950.0, avg_csa_mm2=None, v_target=None)
    session = s.build_session_for_run_all()
    out = run_all(session, dp_ref_inH2O=s.air_dp_ref_inH2O)
    series_int = out["series"]["intake"]
    assert s.csa_min_m2 is not None
    mach = mach_at_min_csa_for_series(series_int, s.csa_min_m2, session.air)
    assert isinstance(mach, list)
    assert len(mach) == len(s.measure_intake)
    assert all((m is not None and 0.0 < m < 1.0) for m in mach)


def test_rpm_from_csa_monotonic_v_target() -> None:
    s = _base_state_with_intake([(1.0, 100.0, 28.0), (2.0, 160.0, 28.0)])
    # set average CSA and two targets
    s.set_csa_from_ui(min_csa_mm2=None, avg_csa_mm2=1200.0, v_target=None)
    session = s.build_session_for_run_all()
    rpm_100 = rpm_from_csa_with_target(s.csa_avg_m2, session.engine, v_target=100.0)
    rpm_120 = rpm_from_csa_with_target(s.csa_avg_m2, session.engine, v_target=120.0)
    assert rpm_100 is not None and rpm_100 > 0
    assert rpm_120 is not None and rpm_120 > rpm_100


ess_common_points = [(1.0, 90.0, 28.0), (2.0, 120.0, 28.0), (3.0, 150.0, 28.0)]


def test_ei_counts_and_range_and_alert_hint() -> None:
    # intake and exhaust with same lifts
    s = _base_state_with_intake([(1.0, 120.0, 28.0), (2.0, 170.0, 28.0), (3.0, 210.0, 28.0)])
    s.lifts_exhaust_mm = [x[0] for x in ess_common_points]
    s.measure_exhaust = [
        {"lift_mm": lift, "q_cfm": q, "dp_inH2O": dp} for (lift, q, dp) in ess_common_points
    ]
    session = s.build_session_for_run_all()
    out = run_all(session, dp_ref_inH2O=s.air_dp_ref_inH2O)
    ei = out["series"].get("ei", [])
    # The EI list should have entries for common lifts
    assert len(ei) == len(ess_common_points)
    vals = [e.get("EI") for e in ei if e.get("EI") is not None]
    m = mean(vals)
    assert 0.5 < m < 1.0
    # Simulate bad exhaust (very low flow) to push EI below 0.70
    s_bad = _base_state_with_intake([(1.0, 120.0, 28.0), (2.0, 170.0, 28.0)])
    s_bad.lifts_exhaust_mm = [1.0, 2.0]
    s_bad.measure_exhaust = [
        {"lift_mm": 1.0, "q_cfm": 60.0, "dp_inH2O": 28.0},
        {"lift_mm": 2.0, "q_cfm": 70.0, "dp_inH2O": 28.0},
    ]
    session_bad = s_bad.build_session_for_run_all()
    out_bad = run_all(session_bad, dp_ref_inH2O=s_bad.air_dp_ref_inH2O)
    ei_bad = out_bad["series"].get("ei", [])
    vals_bad = [e.get("EI") for e in ei_bad if e.get("EI") is not None]
    if vals_bad:
        m_bad = mean(vals_bad)
        assert m_bad < 0.70


def test_ei_threshold_boundaries_no_alert() -> None:
    # Construct intake/exhaust so that EI mean is exactly on boundaries
    s = _base_state_with_intake([(1.0, 140.0, 28.0), (2.0, 200.0, 28.0)])
    # Exhaust chosen so EI ~ 0.70 and 0.85 at two points
    s.lifts_exhaust_mm = [1.0, 2.0]
    s.measure_exhaust = [
        {"lift_mm": 1.0, "q_cfm": 98.0, "dp_inH2O": 28.0},  # 98/140 = 0.70
        {"lift_mm": 2.0, "q_cfm": 170.0, "dp_inH2O": 28.0},  # 170/200 = 0.85
    ]
    session = s.build_session_for_run_all()
    out = run_all(session, dp_ref_inH2O=s.air_dp_ref_inH2O)
    ei = out["series"].get("ei", [])
    vals = [e.get("EI") for e in ei if e.get("EI") is not None]
    # average is (0.70 + 0.85)/2 = 0.775 within bounds
    m = mean(vals)
    assert 0.70 <= m <= 0.85
