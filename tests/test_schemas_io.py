from pathlib import Path
from iop_flow.schemas import (
    AirConditions,
    Engine,
    Geometry,
    LiftPoint,
    FlowSeries,
    CSAProfile,
    Session,
)
from iop_flow.io_json import write_session, read_session


def _sample_session() -> Session:
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
    lifts_int = [
        LiftPoint(lift_mm=1.0, q_cfm=120.0),
        LiftPoint(lift_mm=2.0, q_cfm=175.0),
        LiftPoint(lift_mm=3.0, q_cfm=220.0),
        LiftPoint(lift_mm=4.0, q_cfm=260.0, swirl_rpm=800.0),
        LiftPoint(lift_mm=5.0, q_cfm=290.0),
        LiftPoint(lift_mm=6.0, q_cfm=310.0),
    ]
    lifts_exh = [
        LiftPoint(lift_mm=1.0, q_cfm=90.0),
        LiftPoint(lift_mm=2.0, q_cfm=140.0),
        LiftPoint(lift_mm=3.0, q_cfm=180.0),
        LiftPoint(lift_mm=4.0, q_cfm=210.0),
        LiftPoint(lift_mm=5.0, q_cfm=230.0),
    ]
    series = FlowSeries(intake=lifts_int, exhaust=lifts_exh)
    csa = CSAProfile(min_csa_m2=0.00095, avg_csa_m2=0.00120)
    return Session(
        meta={"project": "demo", "operator": "copilot"},
        mode="baseline",
        air=air,
        engine=eng,
        geom=geom,
        lifts=series,
        csa=csa,
    )


def test_roundtrip_json(tmp_path: Path) -> None:
    s = _sample_session()
    out = tmp_path / "session.json"
    write_session(out, s)
    s2 = read_session(out)
    assert s2 == s


def test_validation_errors() -> None:
    # bore <= 0
    try:
        _ = Geometry(bore_m=0.0, valve_int_m=0.046, valve_exh_m=0.040, throat_m=0.034, stem_m=0.007)
        assert False, "Expected ValueError for bore_m"
    except ValueError:
        pass

    # stem >= throat
    try:
        _ = Geometry(
            bore_m=0.086, valve_int_m=0.046, valve_exh_m=0.040, throat_m=0.007, stem_m=0.007
        )
        assert False, "Expected ValueError for stem_m >= throat_m"
    except ValueError:
        pass


def test_units_contract() -> None:
    # geometria w metrach, lift w mm, Q w CFM
    lp = LiftPoint(lift_mm=2.5, q_cfm=200.0, dp_inH2O=28.0)
    assert lp.lift_mm == 2.5
    assert lp.q_cfm == 200.0
    assert lp.dp_inH2O == 28.0
