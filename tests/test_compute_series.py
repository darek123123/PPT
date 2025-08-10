from iop_flow.schemas import AirConditions, Engine, Geometry, LiftPoint, FlowSeries, Session
from iop_flow.compute_series import compute_series, compute_ei

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


def _session_sample() -> Session:
    intake = [
        LiftPoint(lift_mm=1.0, q_cfm=120.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=2.0, q_cfm=175.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=3.0, q_cfm=220.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=4.0, q_cfm=260.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=5.0, q_cfm=290.0, dp_inH2O=28.0),
    ]
    exhaust = [
        LiftPoint(lift_mm=1.0, q_cfm=90.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=2.0, q_cfm=140.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=3.0, q_cfm=180.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=4.0, q_cfm=210.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=5.0, q_cfm=230.0, dp_inH2O=28.0),
    ]
    fs = FlowSeries(intake=intake, exhaust=exhaust)
    eng = Engine(displ_L=2.0, cylinders=4, ve=0.95)
    return Session(
        meta={"project": "etap5"},
        mode="baseline",
        air=AIR,
        engine=eng,
        geom=GEOM,
        lifts=fs,
        csa=None,
    )


def test_compute_series_intake_has_expected_keys_and_order() -> None:
    s = _session_sample()
    out = compute_series(s, side="intake", a_ref_mode="eff", eff_mode="smoothmin")
    assert len(out) == 5
    # kolejność po liftach 1..5 mm
    assert [round(x["lift_m"], 6) for x in out] == [0.001, 0.002, 0.003, 0.004, 0.005]
    for row in out:
        for key in (
            "A_curtain",
            "A_throat",
            "A_eff",
            "A_ref_key",
            "L_over_D",
            "Cd_ref",
            "V_ref",
            "Mach_ref",
        ):
            assert key in row


def test_compute_series_exhaust_uses_exhaust_valve() -> None:
    s = _session_sample()
    out = compute_series(s, side="exhaust", a_ref_mode="throat")
    # L/D powinno być względem valve_exh_m
    ld = out[2]["L_over_D"]
    assert abs(ld - (0.003 / GEOM.valve_exh_m)) < 1e-12


def test_ei_alignment_and_range() -> None:
    s = _session_sample()
    int_series = compute_series(s, side="intake")
    exh_series = compute_series(s, side="exhaust")
    ei_rows = compute_ei(int_series, exh_series, tol=1e-9)
    assert len(ei_rows) == 5
    # E/I w typowym zakresie 0.6..0.9 dla tych danych
    for r in ei_rows:
        assert 0.5 < r["EI"] < 1.0
