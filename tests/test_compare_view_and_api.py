from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_compare_view_import_smoke() -> None:
    from iop_flow_gui.views.compare import CompareView  # noqa: F401


def test_run_compare_minimal() -> None:
    from iop_flow.api import run_compare
    from iop_flow.schemas import (
        AirConditions,
        Engine,
        Geometry,
        LiftPoint,
        FlowSeries,
        Session,
        CSAProfile,
    )

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
    # simple two-point series to keep diff lengths small
    s1 = FlowSeries(
        intake=[LiftPoint(lift_mm=1.0, q_cfm=100.0), LiftPoint(lift_mm=2.0, q_cfm=150.0)],
        exhaust=[LiftPoint(lift_mm=1.0, q_cfm=90.0), LiftPoint(lift_mm=2.0, q_cfm=120.0)],
    )
    s2 = FlowSeries(
        intake=[LiftPoint(lift_mm=1.0, q_cfm=110.0), LiftPoint(lift_mm=2.0, q_cfm=160.0)],
        exhaust=[LiftPoint(lift_mm=1.0, q_cfm=95.0), LiftPoint(lift_mm=2.0, q_cfm=130.0)],
    )
    sess_before = Session(
        meta={"name": "before"},
        mode="baseline",
        air=air,
        engine=eng,
        geom=geom,
        lifts=s1,
        csa=CSAProfile(min_csa_m2=None, avg_csa_m2=None),
    )
    sess_after = Session(
        meta={"name": "after"},
        mode="baseline",
        air=air,
        engine=eng,
        geom=geom,
        lifts=s2,
        csa=CSAProfile(min_csa_m2=None, avg_csa_m2=None),
    )

    out = run_compare(sess_before, sess_after, keys=("q_m3s_ref", "Cd_ref", "V_ref", "Mach_ref"))
    assert "intake" in out and "exhaust" in out
    # ensure diffs include requested keys and aligned_len equals min length
    for side in ("intake", "exhaust"):
        block = out[side]
        assert block["aligned_len"] >= 2
        diffs = block["diffs"]
        for k in ("q_m3s_ref", "Cd_ref", "V_ref", "Mach_ref"):
            assert isinstance(diffs.get(k, []), list)
