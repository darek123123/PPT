from iop_flow.schemas import (
    AirConditions,
    Engine,
    Geometry,
    LiftPoint,
    FlowSeries,
    Session,
    CSAProfile,
)
from iop_flow.compute_series import compute_series
from iop_flow.engine_link import (
    rpm_limited_by_flow_for_series,
    rpm_from_csa_with_target,
    mach_at_min_csa_for_series,
)

AIR = AirConditions(p_tot=101325.0, T=293.15, RH=0.0)
GEOM = Geometry(
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


def _session_with_csa() -> Session:
    intake = [
        LiftPoint(lift_mm=1.0, q_cfm=120.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=2.0, q_cfm=175.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=3.0, q_cfm=220.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=4.0, q_cfm=260.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=5.0, q_cfm=290.0, dp_inH2O=28.0),
    ]
    fs = FlowSeries(intake=intake, exhaust=[])
    eng = Engine(displ_L=2.0, cylinders=4, ve=0.95)
    csa = CSAProfile(min_csa_m2=0.00095, avg_csa_m2=0.00120)  # tak dobrane, by Mach < 1
    return Session(
        meta={"project": "etap6"},
        mode="baseline",
        air=AIR,
        engine=eng,
        geom=GEOM,
        lifts=fs,
        csa=csa,
    )


def test_rpm_limited_by_flow_monotonicity() -> None:
    s = _session_with_csa()
    series = compute_series(s, side="intake")
    rpm = rpm_limited_by_flow_for_series(series, s.engine, strategy="mean_top_third")
    assert rpm > 0.0

    # Skaluje się z przepływem: ×1.10 -> RPM rośnie
    boosted = [{**r, "q_m3s_ref": r["q_m3s_ref"] * 1.10} for r in series]
    rpm_boost = rpm_limited_by_flow_for_series(boosted, s.engine, strategy="mean_top_third")
    assert rpm_boost > rpm


def test_rpm_from_csa_behaviour() -> None:
    s = _session_with_csa()
    assert s.csa is not None
    assert s.csa.avg_csa_m2 is not None
    rpm_100 = rpm_from_csa_with_target(s.csa.avg_csa_m2, s.engine, v_target=100.0)
    rpm_120 = rpm_from_csa_with_target(s.csa.avg_csa_m2, s.engine, v_target=120.0)
    assert rpm_100 is not None and rpm_120 is not None
    assert rpm_120 > rpm_100  # większa prędkość docelowa -> większe RPM


def test_mach_at_min_csa_below_unity_for_sample() -> None:
    s = _session_with_csa()
    series = compute_series(s, side="intake")
    assert s.csa is not None
    assert s.csa.min_csa_m2 is not None
    mach = mach_at_min_csa_for_series(series, s.csa.min_csa_m2, s.air)
    assert len(mach) == len(series)
    # dla dobranego min-CSA powinno być <1
    assert all(0.0 < m < 1.0 for m in mach)
