from iop_flow.schemas import (
    AirConditions,
    Engine,
    Geometry,
    LiftPoint,
    FlowSeries,
    Session,
    CSAProfile,
)
from iop_flow.api import run_all, run_compare

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


def _session_sample(exhaust: bool = True) -> Session:
    intake = [
        LiftPoint(lift_mm=1.0, q_cfm=120.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=2.0, q_cfm=175.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=3.0, q_cfm=220.0, dp_inH2O=28.0),
    ]
    exh = (
        [
            LiftPoint(lift_mm=1.0, q_cfm=90.0, dp_inH2O=28.0),
            LiftPoint(lift_mm=2.0, q_cfm=140.0, dp_inH2O=28.0),
            LiftPoint(lift_mm=3.0, q_cfm=180.0, dp_inH2O=28.0),
        ]
        if exhaust
        else []
    )
    fs = FlowSeries(intake=intake, exhaust=exh)
    eng = Engine(displ_L=2.0, cylinders=4, ve=0.95)
    csa = CSAProfile(min_csa_m2=0.00095, avg_csa_m2=0.00120)
    return Session(
        meta={"project": "api"}, mode="baseline", air=AIR, engine=eng, geom=GEOM, lifts=fs, csa=csa
    )


def test_run_all_returns_expected_sections() -> None:
    s = _session_sample(exhaust=True)
    out = run_all(s)
    assert "series" in out and "engine" in out
    assert "intake" in out["series"] and "exhaust" in out["series"]
    assert isinstance(out["series"]["ei"], list)
    assert "rpm_flow_limit" in out["engine"]


def test_run_compare_counts_and_keys() -> None:
    before = _session_sample(exhaust=False)
    after = _session_sample(exhaust=False)
    out = run_compare(before, after, keys=("q_m3s_ref", "Cd_ref"))
    assert "intake" in out and "diffs" in out["intake"]
    d = out["intake"]["diffs"]
    assert "q_m3s_ref" in d and "Cd_ref" in d
