from iop_flow.schemas import AirConditions, LiftPoint
from iop_flow.normalize import normalize_lift_point, normalize_series
from iop_flow import formulas as F

AIR = AirConditions(p_tot=101325.0, T=293.15, RH=0.0)


def test_identity_when_same_conditions() -> None:
    lp = LiftPoint(lift_mm=5.0, q_cfm=200.0, dp_inH2O=28.0)
    n = normalize_lift_point(lp, AIR, dp_ref_inH2O=28.0, air_ref=AIR)
    assert abs(n.q_m3s_ref - n.q_m3s_meas) < 1e-9
    assert n.dp_Pa_meas == F.in_h2o_to_pa(28.0)


def test_scaling_by_dp_only() -> None:
    # Ta sama gęstość, inna depresja: skala ~ sqrt(28/10)
    lp = LiftPoint(lift_mm=3.0, q_cfm=200.0, dp_inH2O=10.0)
    n = normalize_lift_point(lp, AIR, dp_ref_inH2O=28.0, air_ref=AIR)
    scale = (28.0 / 10.0) ** 0.5
    assert abs(n.q_m3s_ref / n.q_m3s_meas - scale) < 1e-6


def test_density_and_dp_scaling() -> None:
    # Inna temperatura (inne rho_ref) + inna ΔP
    air_hot = AirConditions(p_tot=101325.0, T=323.15, RH=0.0)  # 50°C
    lp = LiftPoint(lift_mm=4.0, q_cfm=180.0, dp_inH2O=25.0)
    n = normalize_lift_point(lp, AIR, dp_ref_inH2O=28.0, air_ref=air_hot)
    rho_meas = F.air_density(F.AirState(AIR.p_tot, AIR.T, AIR.RH))
    rho_ref = F.air_density(F.AirState(air_hot.p_tot, air_hot.T, air_hot.RH))
    scale = (28.0 / 25.0) ** 0.5 * (rho_meas / rho_ref) ** 0.5
    assert abs(n.q_m3s_ref / n.q_m3s_meas - scale) < 1e-6


def test_no_dp_measured_treated_as_ref() -> None:
    # Brak dp_inH2O => przyjmij dp_meas = dp_ref (brak skalowania po ΔP)
    lp = LiftPoint(lift_mm=2.0, q_cfm=150.0, dp_inH2O=None)
    n = normalize_lift_point(lp, AIR, dp_ref_inH2O=28.0, air_ref=None)
    assert abs(n.q_m3s_ref - n.q_m3s_meas) < 1e-9


def test_series_preserves_order() -> None:
    series = [
        LiftPoint(lift_mm=1.0, q_cfm=100.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=2.0, q_cfm=150.0, dp_inH2O=10.0),
        LiftPoint(lift_mm=3.0, q_cfm=200.0, dp_inH2O=None),
    ]
    out = normalize_series(series, AIR, dp_ref_inH2O=28.0, air_ref=AIR)
    assert [round(x.lift_m, 6) for x in out] == [0.001, 0.002, 0.003]
