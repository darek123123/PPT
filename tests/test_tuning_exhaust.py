"""
Testy funkcji tuningowych wydechu: quarter-wave, CSA, sweep (bez Qt).
"""
from iop_flow.tuning import exhaust_quarter_wave_L_phys, exhaust_quarter_wave_rpm_for_L, collector_csa_from_q

def test_exhaust_quarter_wave():
    # T_exh=700 K, D=38 mm, n=2
    T_exh_K = 700.0
    D = 0.038
    n_harm = 2
    rpm_target = 6500
    # L dla 6500 rpm
    L = exhaust_quarter_wave_L_phys(rpm_target, n_harm, D, T_exh_K)
    assert 0.40 <= L <= 0.85  # 400–850 mm (fizycznie poprawne dla T_exh)
    # rpm dla L=450 mm
    rpm = exhaust_quarter_wave_rpm_for_L(450.0, n_harm, D, T_exh_K)
    assert 6000 <= rpm <= 12000

def test_collector_csa():
    # q=0.04 m³/s, v=70 m/s → CSA≈571 mm² (±10%)
    q = 0.04
    v = 70.0
    csa_m2, csa_mm2 = collector_csa_from_q(q, v)
    assert 514 <= csa_mm2 <= 628  # ±10%
