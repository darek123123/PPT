from iop_flow.schemas import AirConditions, Engine, Geometry, LiftPoint, FlowSeries, Session
from iop_flow.compute_series import compute_series
from iop_flow.compare import align_by_lift, diff_percent, overlay

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
        LiftPoint(lift_mm=1.0, q_cfm=120.0),
        LiftPoint(lift_mm=2.0, q_cfm=175.0),
        LiftPoint(lift_mm=3.0, q_cfm=220.0),
        LiftPoint(lift_mm=4.0, q_cfm=260.0),
        LiftPoint(lift_mm=5.0, q_cfm=290.0),
    ]
    fs = FlowSeries(intake=intake, exhaust=[])
    eng = Engine(displ_L=2.0, cylinders=4, ve=0.95)
    return Session(
        meta={"project": "cmp"}, mode="baseline", air=AIR, engine=eng, geom=GEOM, lifts=fs, csa=None
    )


def test_align_by_lift_matches_points() -> None:
    s = _session_sample()
    before = compute_series(s, side="intake")
    # „after” = te same lifty, ale Q podbite o 10%
    after = [{**r, "q_m3s_ref": r["q_m3s_ref"] * 1.10} for r in before]
    aligned = align_by_lift(before, after, tol=1e-9)
    assert len(aligned) == len(before)
    # w każdej parze lifty praktycznie identyczne
    assert all(abs(a["lift_m"] - b["lift_m"]) < 1e-12 for a, b in aligned)


def test_diff_percent_linear_for_q_and_cd() -> None:
    s = _session_sample()
    before = compute_series(s, side="intake", a_ref_mode="throat")  # stałe A_ref
    after = [{**r, "q_m3s_ref": r["q_m3s_ref"] * 1.10} for r in before]
    aligned = align_by_lift(before, after)
    # Q: +10%
    rows_q = diff_percent(aligned, "q_m3s_ref")
    assert all(9.9 <= r["delta_pct"] <= 10.1 for r in rows_q)
    # Cd: liniowe z Q (A_ref, ΔP, ρ stałe) => też ok. +10%
    rows_cd = diff_percent(aligned, "Cd_ref")
    assert all(9.0 <= r["delta_pct"] <= 11.0 for r in rows_cd)


def test_overlay_builds_rows_for_multiple_series() -> None:
    s = _session_sample()
    series1 = compute_series(s, side="intake")
    series2 = [{**r, "q_m3s_ref": r["q_m3s_ref"] * 1.05} for r in series1]
    ov = overlay([series1, series2], keys=("q_m3s_ref", "Cd_ref"))
    # 2 serie * 5 punktów = 10 rekordów
    assert len(ov) == 10
    # pierwsze 5 to series_idx=0, kolejne 5 to series_idx=1
    assert all(row["series_idx"] in (0, 1) for row in ov)
