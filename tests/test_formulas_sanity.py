from iop_flow.formulas import (
    air_density,
    AIR_STD_28IN,
    area_throat,
    area_curtain,
    area_eff_smoothmin,
    cfm_to_m3s,
    in_h2o_to_pa,
    cd,
)


def test_air_density_range() -> None:
    rho = air_density(AIR_STD_28IN)
    assert 1.15 <= rho <= 1.25


def test_cd_sanity_si_units() -> None:
    """
    Wszystkie długości w METRACH.
    Przypadek tak dobrany, by Cd był ~1.0–1.25 (typowe, odniesienie do throat).
    """
    # 300 CFM @ 28" H2O
    q_m3s = cfm_to_m3s(300.0)
    dp_ref = in_h2o_to_pa(28.0)
    rho = air_density(AIR_STD_28IN)

    # Throat/stem w METRACH: 38 mm / 7 mm
    A_t = area_throat(0.038, 0.007)
    Cd_val = cd(q_m3s, A_t, dp_ref, rho)
    print(f"Cd_38 = {Cd_val:.3f}")

    # Spodziewane ~1.20 (tolerancja szeroka dla różnych środowisk)
    assert 0.8 < Cd_val < 1.25, f"Cd out of expected range: {Cd_val:.3f}"


def test_area_and_efficiency_monotonic() -> None:
    # Dane w METRACH: valve 46 mm, lift 10 mm; throat 34 mm / stem 7 mm
    A_c = area_curtain(0.046, 0.010)
    A_t = area_throat(0.034, 0.007)
    A_eff = area_eff_smoothmin(A_c, A_t)

    assert A_c > 0.0
    # A_eff powinno być bliżej mniejszego z (A_c, A_t)
    assert min(A_c, A_t) * 0.8 <= A_eff <= min(A_c, A_t) * 1.01


def test_cd_increases_when_throat_shrinks() -> None:
    """
    Test kierunku zmiany: przy tej samej objętości Q, mniejsze A_ref -> większe Cd.
    """
    q_m3s = cfm_to_m3s(300.0)
    dp_ref = in_h2o_to_pa(28.0)
    rho = air_density(AIR_STD_28IN)

    Cd_38 = cd(q_m3s, area_throat(0.038, 0.007), dp_ref, rho)
    Cd_34 = cd(q_m3s, area_throat(0.034, 0.007), dp_ref, rho)
    print(f"Cd_38 = {Cd_38:.3f}, Cd_34 = {Cd_34:.3f}")
    assert Cd_34 > Cd_38
