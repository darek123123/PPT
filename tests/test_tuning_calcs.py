"""
Testy funkcji tuningowych: quarter-wave i Helmholtz (bez Qt).
"""
from iop_flow.tuning import quarter_wave_L_phys, quarter_wave_rpm_for_L, helmholtz_f_and_rpm

def test_quarter_wave_and_helmholtz():
    # Dane testowe
    T_K = 293.15
    D_m = 0.05
    L_m = 0.30
    n_harm = 2
    rpm_target = 6500
    V_plenum_m3 = 0.0035

    # Ćwierćfala: zalecane L dla rpm_target
    L_recommended = quarter_wave_L_phys(rpm_target, n_harm, D_m, T_K)
    assert 0.25 <= L_recommended <= 0.55  # 250–550 mm (fizycznie poprawne)

    # rpm dla zadanego L
    rpm_for_L = quarter_wave_rpm_for_L(L_m, n_harm, D_m, T_K)
    assert 2000 <= rpm_for_L <= 11000  # sensowny zakres

    # Helmholtz
    f_H, rpm_helm = helmholtz_f_and_rpm(D_m, L_m, V_plenum_m3, n_harm, T_K)
    assert 50 <= f_H <= 200
    assert 1000 <= rpm_helm <= 20000
